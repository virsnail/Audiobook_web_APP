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

  interface Props {
    currentGlobalTime?: number; // 当前全局播放时间
    isPlaying?: boolean; // 音频是否正在播放
    onSeekTo?: (globalTime: number, chapterIndex: number) => void;
  }

  let { currentGlobalTime = 0, isPlaying = false, onSeekTo }: Props = $props();

  let containerRef: HTMLElement | null = $state(null);
  let chapterRefs: Map<number, HTMLElement> = new Map();
  let observer: IntersectionObserver | null = null;

  // 当前高亮的 segment 全局 ID
  let currentHighlightId = $state(-1);

  // HTML 转义
  function escapeHtml(text: string): string {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // 渲染单个章节的 HTML
  function renderChapter(chapter: Chapter): string {
    const { textContent, segments } = chapter;

    if (!textContent) {
      return '<div class="chapter-placeholder">加载中...</div>';
    }

    if (!segments || segments.length === 0) {
      // 没有对齐数据，简单渲染文本
      const lines = textContent.split("\n").filter((l) => l.trim());
      return lines.map((line) => `<p>${escapeHtml(line)}</p>`).join("\n");
    }

    // 有对齐数据，精确匹配渲染
    let result = "";
    let textPos = 0;

    for (const seg of segments) {
      const foundIndex = textContent.indexOf(seg.text, textPos);

      if (foundIndex !== -1) {
        // 添加未匹配的文本
        if (foundIndex > textPos) {
          result += escapeHtml(textContent.substring(textPos, foundIndex));
        }

        // 添加可点击的 segment
        const globalId = seg.globalId ?? -1;
        const globalStart = seg.globalStart ?? 0;
        result += `<span class="segment" data-global-id="${globalId}" data-global-start="${globalStart}">${escapeHtml(seg.text)}</span>`;

        textPos = foundIndex + seg.text.length;
      }
    }

    // 剩余文本
    if (textPos < textContent.length) {
      result += escapeHtml(textContent.substring(textPos));
    }

    // 转换为段落
    return result
      .split("\n")
      .filter((p) => p.trim())
      .map((p) => `<p>${p}</p>`)
      .join("\n");
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

  // 更新高亮
  function updateHighlight() {
    if (!containerRef) return;

    // 移除旧高亮
    const oldHighlight = containerRef.querySelector(".segment.active");
    if (oldHighlight) {
      oldHighlight.classList.remove("active");
    }

    // 找到当前时间对应的 segment
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
      );
      if (newHighlight !== oldHighlight) {
        oldHighlight?.classList.remove("active");
        newHighlight?.classList.add("active");

        // 移除自动滚动，改为手动触发
        // if (isPlaying && newHighlight) { ... }
      }
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

  onDestroy(() => {
    observer?.disconnect();
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
