<!--
  全书文本内容组件（单页面显示所有章节）
  
  功能：
  - 显示所有章节的文本
  - IntersectionObserver 监听章节可见性
  - 滚动到某章节时自动加载数据
  - 点击任何词语跳转到对应音频位置
  - 根据当前播放时间高亮词语
-->
<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { chaptersStore } from "$lib/stores/chapters.svelte";
  import type { Chapter } from "$lib/types/chapter";

  // 语法高亮（onMount 中异步加载，出错时优雅降级为纯文本）
  let hljs: any = $state(null);

  /**
   * 异步初始化 highlight.js（在 onMount 中调用）
   * 加载完成后，hljs 状态更新会触发已渲染代码块的重新高亮
   */
  async function initHighlightJs() {
    try {
      const mod = await import("highlight.js/lib/core");
      const core = mod.default;

      // 注册常用语言
      const langs: [string, () => Promise<any>][] = [
        ["python", () => import("highlight.js/lib/languages/python")],
        [
          "javascript",
          () => import("highlight.js/lib/languages/javascript"),
        ],
        [
          "typescript",
          () => import("highlight.js/lib/languages/typescript"),
        ],
        ["bash", () => import("highlight.js/lib/languages/bash")],
        ["shell", () => import("highlight.js/lib/languages/shell")],
        ["json", () => import("highlight.js/lib/languages/json")],
        ["xml", () => import("highlight.js/lib/languages/xml")],
        ["css", () => import("highlight.js/lib/languages/css")],
        ["sql", () => import("highlight.js/lib/languages/sql")],
        ["java", () => import("highlight.js/lib/languages/java")],
        ["c", () => import("highlight.js/lib/languages/c")],
        ["cpp", () => import("highlight.js/lib/languages/cpp")],
        ["go", () => import("highlight.js/lib/languages/go")],
        ["rust", () => import("highlight.js/lib/languages/rust")],
        ["yaml", () => import("highlight.js/lib/languages/yaml")],
        [
          "markdown",
          () => import("highlight.js/lib/languages/markdown"),
        ],
        ["diff", () => import("highlight.js/lib/languages/diff")],
        ["http", () => import("highlight.js/lib/languages/http")],
      ];
      for (const [name, loader] of langs) {
        try {
          const langMod = await loader();
          core.registerLanguage(name, langMod.default);
        } catch {
          /* 忽略单个语言注册失败 */
        }
      }
      // 常见别名
      core.registerAliases(["py"], { languageName: "python" });
      core.registerAliases(["js"], { languageName: "javascript" });
      core.registerAliases(["ts"], { languageName: "typescript" });
      core.registerAliases(["sh", "zsh"], { languageName: "bash" });
      core.registerAliases(["html", "htm", "xhtml"], {
        languageName: "xml",
      });
      core.registerAliases(["yml"], { languageName: "yaml" });
      core.registerAliases(["md"], { languageName: "markdown" });

      // 赋值触发响应式更新，使已渲染的代码块重新高亮
      hljs = core;
    } catch {
      hljs = null; // highlight.js 加载失败，降级为纯文本
    }
  }

  interface Props {
    currentGlobalTime?: number; // 当前全局播放时间
    isPlaying?: boolean; // 音频是否正在播放
    autoScroll?: boolean; // 是否随播放自动滚动到当前句
    onSeekTo?: (globalTime: number, chapterIndex: number) => void;
  }

  let { currentGlobalTime = 0, isPlaying = false, autoScroll = false, onSeekTo }: Props = $props();

  let containerRef: HTMLElement | null = $state(null);
  let chapterRefs: Map<number, HTMLElement> = new Map();
  let observer: IntersectionObserver | null = null;

  // 当前高亮的 segment 全局 ID
  let currentHighlightId = $state(-1);

  // ========== 安全限制常量 ==========
  // 防止超大文本或异常数据导致浏览器卡死
  const SAFETY_LIMITS = {
    MAX_TEXT_LENGTH: 500_000,      // 单章节最大字符数（500KB）
    MAX_LINES: 20_000,             // formatWithCodeBlocks 最大处理行数
    MAX_CODE_LINES: 5_000,         // 单个代码块最大行数
    MAX_SEGMENTS: 10_000,          // renderChapter 最大 segment 数
    MAX_CODE_BLOCKS_HIGHLIGHT: 100,// hljs 单次最大高亮代码块数
    MAX_RENDER_TIME_MS: 3_000,     // 单次渲染超时（毫秒）
    HIGHLIGHT_THROTTLE_MS: 250,    // updateHighlight 节流间隔
  } as const;

  // HTML 转义
  function escapeHtml(text: string): string {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // HTML 反转义（用于将已转义文本还原后传给 highlight.js）
  function unescapeHtml(text: string): string {
    return text
      .replace(/&#039;/g, "'")
      .replace(/&quot;/g, '"')
      .replace(/&gt;/g, ">")
      .replace(/&lt;/g, "<")
      .replace(/&amp;/g, "&");
  }

  /**
   * 尝试对代码进行语法高亮，失败时返回原始已转义的代码
   * 注意：输入 code 是 HTML 转义后的文本，需要先反转义再交给 hljs
   * hljs 的输出自带 HTML 转义，无需再次处理
   */
  function tryHighlight(code: string, language: string): string {
    if (!hljs || !language) return code;
    try {
      const langLower = language.toLowerCase();
      if (hljs.getLanguage(langLower)) {
        const rawCode = unescapeHtml(code);
        return hljs.highlight(rawCode, { language: langLower }).value;
      }
    } catch {
      /* 高亮失败，降级为纯文本 */
    }
    return code;
  }

  /**
   * 删除代码块中的所有空白行
   */
  function removeBlankLines(lines: string[]): string[] {
    return lines.filter((line) => line.trim() !== "");
  }

  /**
   * 构建代码块的 HTML
   */
  function buildCodeBlockHtml(
    codeLines: string[],
    codeLanguage: string,
  ): string {
    const langAttr = codeLanguage
      ? ` data-language="${escapeHtml(codeLanguage)}"`
      : "";
    let html = `<div class="code-block"${langAttr}>`;
    if (codeLanguage) {
      html += `<div class="code-lang">${escapeHtml(codeLanguage)}</div>`;
    }
    // 删除空白行后拼接，再尝试语法高亮
    const compacted = removeBlankLines(codeLines);
    const rawCode = compacted.join("\n");
    const highlightedCode = codeLanguage
      ? tryHighlight(rawCode, codeLanguage)
      : rawCode;
    html += `<pre><code>${highlightedCode}</code></pre></div>`;
    return html;
  }

  /**
   * 将原始 HTML 字符串转换为段落，支持 Markdown 代码块（```...```）和行内代码（`...`）
   * 内含安全限制：超过最大行数或超时时停止处理
   */
  function formatWithCodeBlocks(rawHtml: string): string {
    const lines = rawHtml.split("\n");
    let output = "";
    let inCodeBlock = false;
    let codeLines: string[] = [];
    let codeLanguage = "";

    // 安全限制：行数检查
    const maxLines = Math.min(lines.length, SAFETY_LIMITS.MAX_LINES);
    if (lines.length > SAFETY_LIMITS.MAX_LINES) {
      console.warn(`[安全限制] formatWithCodeBlocks: 文本行数 ${lines.length} 超过限制 ${SAFETY_LIMITS.MAX_LINES}，截断处理`);
    }

    const startTime = performance.now();

    for (let idx = 0; idx < maxLines; idx++) {
      // 安全限制：超时检查（每 500 行检查一次）
      if (idx > 0 && idx % 500 === 0) {
        if (performance.now() - startTime > SAFETY_LIMITS.MAX_RENDER_TIME_MS) {
          console.warn(`[安全限制] formatWithCodeBlocks: 处理耗时超过 ${SAFETY_LIMITS.MAX_RENDER_TIME_MS}ms，已处理 ${idx}/${maxLines} 行，停止`);
          break;
        }
      }

      const line = lines[idx];
      // 提取纯文本（去掉 HTML 标签）来检测 ```
      const plainLine = line.replace(/<[^>]+>/g, "").trim();

      if (!inCodeBlock && plainLine.startsWith("```")) {
        // 代码块开始
        inCodeBlock = true;
        codeLanguage = plainLine.slice(3).trim();
        codeLines = [];
      } else if (inCodeBlock && plainLine === "```") {
        // 代码块结束
        inCodeBlock = false;
        output += buildCodeBlockHtml(codeLines, codeLanguage);
        codeLanguage = "";
        codeLines = [];
      } else if (inCodeBlock) {
        // 安全限制：单个代码块行数
        if (codeLines.length < SAFETY_LIMITS.MAX_CODE_LINES) {
          codeLines.push(line);
        }
      } else {
        if (line.trim()) {
          // 处理行内代码：`...` → <code class="inline-code">...</code>
          const processedLine = line.replace(
            /`([^`]+)`/g,
            '<code class="inline-code">$1</code>',
          );
          output += `<p>${processedLine}</p>`;
        }
      }
    }

    // 处理未闭合的代码块
    if (inCodeBlock && codeLines.length > 0) {
      output += buildCodeBlockHtml(codeLines, codeLanguage);
    }

    return output;
  }

  // 渲染单个章节的 HTML（含安全限制）
  function renderChapter(chapter: Chapter): string {
    const { textContent, segments } = chapter;

    if (!textContent) {
      return '<div class="chapter-placeholder">加载中... Loading...</div>';
    }

    // 安全限制：文本长度检查
    let safeText = textContent;
    if (textContent.length > SAFETY_LIMITS.MAX_TEXT_LENGTH) {
      console.warn(`[安全限制] renderChapter: 文本长度 ${textContent.length} 超过限制 ${SAFETY_LIMITS.MAX_TEXT_LENGTH}，截断处理`);
      safeText = textContent.substring(0, SAFETY_LIMITS.MAX_TEXT_LENGTH) + "\n\n[... 文本过长，已截断 ...]";
    }

    if (!segments || segments.length === 0) {
      // 没有对齐数据，简单渲染文本（支持代码块）
      const escaped = safeText
        .split("\n")
        .map((line) => escapeHtml(line))
        .join("\n");
      return formatWithCodeBlocks(escaped);
    }

    // 安全限制：segment 数量检查
    const safeSegments = segments.length > SAFETY_LIMITS.MAX_SEGMENTS
      ? segments.slice(0, SAFETY_LIMITS.MAX_SEGMENTS)
      : segments;
    if (segments.length > SAFETY_LIMITS.MAX_SEGMENTS) {
      console.warn(`[安全限制] renderChapter: segment 数量 ${segments.length} 超过限制 ${SAFETY_LIMITS.MAX_SEGMENTS}，截断处理`);
    }

    // 有对齐数据，精确匹配渲染
    let result = "";
    let textPos = 0;
    const startTime = performance.now();

    for (let i = 0; i < safeSegments.length; i++) {
      // 安全限制：超时检查（每 500 个 segment 检查一次）
      if (i > 0 && i % 500 === 0) {
        if (performance.now() - startTime > SAFETY_LIMITS.MAX_RENDER_TIME_MS) {
          console.warn(`[安全限制] renderChapter: segment 匹配耗时超过 ${SAFETY_LIMITS.MAX_RENDER_TIME_MS}ms，已处理 ${i}/${safeSegments.length}，停止`);
          break;
        }
      }

      const seg = safeSegments[i];
      const foundIndex = safeText.indexOf(seg.text, textPos);

      if (foundIndex !== -1) {
        // 添加未匹配的文本
        if (foundIndex > textPos) {
          result += escapeHtml(safeText.substring(textPos, foundIndex));
        }

        // 添加可点击的 segment
        const globalId = seg.globalId ?? -1;
        const globalStart = seg.globalStart ?? 0;
        result += `<span class="segment" data-global-id="${globalId}" data-global-start="${globalStart}">${escapeHtml(seg.text)}</span>`;

        textPos = foundIndex + seg.text.length;
      }
    }

    // 剩余文本
    if (textPos < safeText.length) {
      result += escapeHtml(safeText.substring(textPos));
    }

    // 转换为段落（支持代码块）
    return formatWithCodeBlocks(result);
  }

  // 处理章节可见性变化
  function handleIntersection(entries: IntersectionObserverEntry[]) {
    entries.forEach((entry) => {
      const chapterIndex = parseInt(
        (entry.target as HTMLElement).dataset.chapterIndex || "-1",
      );
      if (chapterIndex < 0) return;

      const isVisible = entry.isIntersecting;
      chaptersStore.setChapterVisibility(chapterIndex, isVisible);

      if (isVisible) {
        // 章节可见
        // Data is preloaded by loadAllBookData, so just track visibility
      } else {
        // 章节不可见
        // No unloading needed for "load all" pattern
      }
    });
  }

  // 更新高亮（含节流保护）
  let _highlightTimer: ReturnType<typeof setTimeout> | null = null;
  let _lastHighlightTime = 0;

  /** 将当前高亮元素滚动到视口内（约 35% 处），自动滚动模式下使用瞬时滚动避免被取消 */
  function scrollHighlightIntoView(el: HTMLElement) {
    const rect = el.getBoundingClientRect();
    const absoluteTop = window.scrollY + rect.top;
    const targetScroll = absoluteTop - window.innerHeight * 0.35;
    const clamped = Math.max(0, targetScroll);
    window.scrollTo({
      top: clamped,
      behavior: autoScroll ? "auto" : "smooth",
    });
  }

  /** 当前高亮是否在“舒适可见”区域内（约视口 15%～85%），用于自动滚动时判断是否需要跟滚 */
  function isHighlightInComfortZone(el: HTMLElement): boolean {
    const rect = el.getBoundingClientRect();
    const vh = window.innerHeight;
    const top = rect.top;
    const bottom = rect.bottom;
    return top >= vh * 0.15 && bottom <= vh * 0.85;
  }

  /** 判断是否为“新的一行”（垂直位置变化超过阈值），用于自动滚动时按行跟滚，避免整段一大块只滚一次 */
  function isNewScrollLine(newEl: HTMLElement, oldEl: HTMLElement | null): boolean {
    if (!oldEl) return true;
    const newTop = newEl.getBoundingClientRect().top;
    const oldTop = oldEl.getBoundingClientRect().top;
    return Math.abs(newTop - oldTop) > 18;
  }

  function updateHighlight() {
    if (!containerRef) return;

    const throttleMs = autoScroll && isPlaying ? 80 : SAFETY_LIMITS.HIGHLIGHT_THROTTLE_MS;
    const now = performance.now();
    if (now - _lastHighlightTime < throttleMs) {
      if (_highlightTimer) clearTimeout(_highlightTimer);
      _highlightTimer = setTimeout(updateHighlight, throttleMs);
      return;
    }
    _lastHighlightTime = now;
    _highlightTimer = null;

    const oldHighlight = containerRef.querySelector(".segment.active") as HTMLElement | null;
    if (oldHighlight) {
      oldHighlight.classList.remove("active");
    }

    const { chapterIndex, chapterTime } =
      chaptersStore.globalToChapterTime(currentGlobalTime);
    const chapter = chaptersStore.chapters[chapterIndex];

    if (!chapter?.segments) return;

    const currentSeg = chapter.segments.find(
      (s) => chapterTime >= s.start && chapterTime <= s.end,
    );

    if (currentSeg && currentSeg.globalId !== undefined) {
      currentHighlightId = currentSeg.globalId;

      const newHighlight = containerRef.querySelector(
        `[data-global-id="${currentSeg.globalId}"]`,
      ) as HTMLElement | null;

      if (newHighlight) {
        if (newHighlight !== oldHighlight) {
          oldHighlight?.classList.remove("active");
          newHighlight.classList.add("active");
        }

        if (autoScroll && isPlaying) {
          const isNewLine = isNewScrollLine(newHighlight, oldHighlight);
          if (isNewLine && !isHighlightInComfortZone(newHighlight)) {
            scrollHighlightIntoView(newHighlight);
          }
        }
      }
    }
  }

  // 暴露给父组件：滚动到指定 segment（用于书签跳转）
  export function scrollToSegment(globalSegmentId: number) {
    if (!containerRef) return;
    const el = containerRef.querySelector(`[data-global-id="${globalSegmentId}"]`);
    if (el) {
      const rect = (el as HTMLElement).getBoundingClientRect();
      const absoluteTop = window.scrollY + rect.top;
      const targetScroll = absoluteTop - window.innerHeight * 0.35;
      window.scrollTo({
        top: Math.max(0, targetScroll),
        behavior: "smooth",
      });
    }
  }

  // 暴露给父组件：手动滚动到当前高亮位置
  export function scrollToCurrent() {
    if (!containerRef) return;

    // 重新查找当前高亮元素 (使用 currentHighlightId)
    // 注意：updateHighlight 更新了 active class，但这里直接查找 ID 更稳健
    let targetId = currentHighlightId;

    // 如果没有高亮，尝试根据当前时间查找
    if (targetId === -1) {
      const { chapterIndex, chapterTime } =
        chaptersStore.globalToChapterTime(currentGlobalTime);
      const chapter = chaptersStore.chapters[chapterIndex];
      const seg = chapter?.segments?.find(
        (s) => chapterTime >= s.start && chapterTime <= s.end,
      );
      if (seg?.globalId !== undefined) targetId = seg.globalId;
    }

    if (targetId !== -1) {
      const el = containerRef.querySelector(`[data-global-id="${targetId}"]`);
      if (el) {
        const rect = el.getBoundingClientRect();
        const absoluteTop = window.scrollY + rect.top;
        const targetScroll = absoluteTop - window.innerHeight * 0.4; // 垂直居中偏上

        window.scrollTo({
          top: Math.max(0, targetScroll),
          behavior: "smooth",
        });
      }
    }
  }

  // 点击处理
  function handleClick(event: MouseEvent) {
    const target = event.target as HTMLElement;
    const segment = target.closest(".segment") as HTMLElement;

    if (segment && onSeekTo) {
      const globalStart = parseFloat(segment.dataset.globalStart || "0");
      const chapterIndex =
        chaptersStore.getChapterIndexByGlobalTime(globalStart);
      onSeekTo(globalStart, chapterIndex);
    }
  }

  // 设置 IntersectionObserver
  function setupChapterObserver(node: HTMLElement, chapterIndex: number) {
    chapterRefs.set(chapterIndex, node);

    if (!observer) {
      observer = new IntersectionObserver(handleIntersection, {
        root: null,
        rootMargin: "200px",
        threshold: 0.1,
      });
    }

    observer.observe(node);

    return {
      destroy() {
        observer?.unobserve(node);
        chapterRefs.delete(chapterIndex);
      },
    };
  }

  // 监听时间变化
  $effect(() => {
    const _ = currentGlobalTime;
    updateHighlight();
  });

  // hljs 加载完成后，对页面上已有的代码块进行语法高亮（含数量限制）
  $effect(() => {
    if (hljs && containerRef) {
      const blocks = containerRef.querySelectorAll(".code-block pre code:not(.hljs)");
      const maxBlocks = Math.min(blocks.length, SAFETY_LIMITS.MAX_CODE_BLOCKS_HIGHLIGHT);
      if (blocks.length > SAFETY_LIMITS.MAX_CODE_BLOCKS_HIGHLIGHT) {
        console.warn(`[安全限制] hljs: 代码块数量 ${blocks.length} 超过限制 ${SAFETY_LIMITS.MAX_CODE_BLOCKS_HIGHLIGHT}，仅高亮前 ${maxBlocks} 个`);
      }

      for (let i = 0; i < maxBlocks; i++) {
        const block = blocks[i];
        const lang = (
          block.closest(".code-block") as HTMLElement
        )?.dataset.language;
        if (lang) {
          try {
            const langLower = lang.toLowerCase();
            if (hljs.getLanguage(langLower)) {
              const raw = block.textContent || "";
              // 安全限制：单个代码块内容过大时跳过高亮
              if (raw.length > 50_000) {
                console.warn(`[安全限制] hljs: 代码块内容过大 (${raw.length} 字符)，跳过高亮`);
                block.classList.add("hljs"); // 标记为已处理，避免反复尝试
                continue;
              }
              const highlighted = hljs.highlight(raw, {
                language: langLower,
              }).value;
              block.innerHTML = highlighted;
              block.classList.add("hljs");
            }
          } catch {
            /* 高亮失败，保持原样 */
            block.classList.add("hljs"); // 标记为已处理
          }
        }
      }
    }
  });

  onMount(() => {
    // 异步加载 highlight.js（不阻塞首屏渲染）
    initHighlightJs();
  });

  onDestroy(() => {
    observer?.disconnect();
    // 清理节流定时器
    if (_highlightTimer) {
      clearTimeout(_highlightTimer);
      _highlightTimer = null;
    }
  });
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div
  bind:this={containerRef}
  class="reader-container"
  onclick={handleClick}
  role="document"
>
  {#each chaptersStore.chapters as chapter, index (chapter.id)}
    <section
      class="chapter"
      data-chapter-index={index}
      use:setupChapterObserver={index}
    >
      <!-- 章节内容 -->
      <div class="chapter-content">
        {@html renderChapter(chapter)}
      </div>
    </section>
  {/each}
</div>

<style>
  .reader-container {
    max-width: 800px;
    margin: 0 auto;
    padding: 80px 24px 160px;
    /* Font size handled by app.css var */
    /* font-size: 1.125rem; */
    /* Color handled by app.css var */
    /* color: #1a1a1a; */
    color: inherit;
  }

  .chapter {
    margin-bottom: 48px;
  }

  .chapter-header {
    margin-bottom: 24px;
    padding-bottom: 12px;
    border-bottom: 2px solid #e5e7eb;
  }

  .chapter-number {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--reader-muted); /* Use var */
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .chapter-content :global(p) {
    margin-bottom: 1.25em;
    text-indent: 2em;
  }

  /* 代码块样式 */
  .chapter-content :global(.code-block) {
    background-color: var(--reader-code-bg, #f6f8fa);
    border: 1px solid var(--reader-code-border, #e1e4e8);
    border-radius: 6px;
    margin: 1em 0;
    overflow-x: auto;
    line-height: var(--reader-code-line-height, 1.25); /* 在容器级重置行高，覆盖 .reader-container 的 1.8 */
  }

  .chapter-content :global(.code-block .code-lang) {
    padding: 2px 12px;
    font-size: var(--reader-code-font-size, 0.75em);
    color: var(--reader-muted, #6a737d);
    border-bottom: 1px solid var(--reader-code-border, #e1e4e8);
    font-family:
      "JetBrains Mono",
      "Fira Code",
      "SF Mono",
      "Cascadia Code",
      "Source Code Pro",
      Menlo,
      Consolas,
      "Liberation Mono",
      monospace;
  }

  .chapter-content :global(.code-block pre) {
    margin: 0;
    padding: var(--reader-code-padding, 10px 14px);
  }

  .chapter-content :global(.code-block code) {
    font-family:
      "JetBrains Mono",
      "Fira Code",
      "SF Mono",
      "Cascadia Code",
      "Source Code Pro",
      Menlo,
      Consolas,
      "Liberation Mono",
      monospace;
    font-size: var(--reader-code-font-size, 0.75em);
    line-height: var(--reader-code-line-height, 1.25);
    white-space: pre;
    color: inherit;
  }

  /* 行内代码样式 */
  .chapter-content :global(.inline-code) {
    font-family:
      "JetBrains Mono",
      "Fira Code",
      "SF Mono",
      "Cascadia Code",
      "Source Code Pro",
      Menlo,
      Consolas,
      "Liberation Mono",
      monospace;
    background-color: var(--reader-code-bg, #f6f8fa);
    padding: 0.1em 0.35em;
    border-radius: 3px;
    font-size: var(--reader-code-font-size, 0.75em);
  }

  /* ===== 语法高亮颜色 (GitHub 风格) ===== */
  .chapter-content :global(.code-block .hljs-keyword),
  .chapter-content :global(.code-block .hljs-selector-tag),
  .chapter-content :global(.code-block .hljs-deletion) {
    color: var(--hljs-keyword, #d73a49);
  }
  .chapter-content :global(.code-block .hljs-string),
  .chapter-content :global(.code-block .hljs-addition) {
    color: var(--hljs-string, #032f62);
  }
  .chapter-content :global(.code-block .hljs-comment),
  .chapter-content :global(.code-block .hljs-quote) {
    color: var(--hljs-comment, #6a737d);
    font-style: italic;
  }
  .chapter-content :global(.code-block .hljs-title),
  .chapter-content :global(.code-block .hljs-title.function_),
  .chapter-content :global(.code-block .hljs-section) {
    color: var(--hljs-function, #6f42c1);
  }
  .chapter-content :global(.code-block .hljs-number),
  .chapter-content :global(.code-block .hljs-literal) {
    color: var(--hljs-number, #005cc5);
  }
  .chapter-content :global(.code-block .hljs-built_in),
  .chapter-content :global(.code-block .hljs-type) {
    color: var(--hljs-builtin, #e36209);
  }
  .chapter-content :global(.code-block .hljs-attr),
  .chapter-content :global(.code-block .hljs-attribute) {
    color: var(--hljs-attr, #005cc5);
  }
  .chapter-content :global(.code-block .hljs-variable),
  .chapter-content :global(.code-block .hljs-template-variable) {
    color: var(--hljs-variable, #e36209);
  }
  .chapter-content :global(.code-block .hljs-params) {
    color: inherit;
  }
  .chapter-content :global(.code-block .hljs-meta) {
    color: var(--hljs-meta, #005cc5);
  }
  .chapter-content :global(.code-block .hljs-regexp) {
    color: var(--hljs-string, #032f62);
  }

  .chapter-placeholder {
    padding: 40px 20px;
    text-align: center;
    color: var(--reader-muted);
    font-style: italic;
  }

  .reader-container :global(.segment) {
    cursor: pointer;
    border-radius: 2px;
    transition: background-color 0.2s ease;
  }

  .reader-container :global(.segment:hover) {
    background-color: var(--reader-highlight-hover);
  }

  .reader-container :global(.segment.active) {
    background-color: var(--reader-highlight);
    box-shadow: 0 0 0 2px var(--reader-highlight-hover);
  }

  /* 移除组件内 Dark Mode 媒体查询，完全由 app.css 控制 */

  /* 移动端 */
  @media (max-width: 640px) {
    .reader-container {
      padding: 70px 16px 140px;
      /* font-size: 1rem; -- Managed by var */
    }

    .chapter {
      margin-bottom: 32px;
    }
  }
</style>
