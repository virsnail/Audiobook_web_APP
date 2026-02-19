<!--
  阅读器主页面（单页面全书显示）
  
  功能：
  - 顶部导航栏
  - 主体：全书文本内容（所有章节）
  - 底部：音频播放器
  - 自动加载/卸载章节数据
  - 点击文字跳转音频
-->
<script lang="ts">
  import { onMount, tick, untrack } from "svelte";
  import AudioPlayer from "$lib/components/AudioPlayer.svelte";
  import TextContent from "$lib/components/TextContent.svelte";
  import { chaptersStore } from "$lib/stores/chapters.svelte";
  import {
    logActivity,
    getBookmarks,
    createBookmark,
    deleteBookmark,
    type BookmarkItem,
  } from "$lib/utils/api";
  import type { BookManifest, Segment } from "$lib/types/chapter";

  interface PageData {
    bookId: string;
    manifest: BookManifest;
    basePath: string;
    firstChapter: {
      id: string;
      textContent: string;
      segments: Segment[];
    };
    bookTitle: string;
    processingStatus?: string;
    processingError?: string;
  }

  let { data }: { data: PageData } = $props();

  // 使用 $effect 响应数据更新并初始化
  $effect(() => {
    // 显式依赖追踪
    const manifest = data?.manifest;
    const basePath = data?.basePath;
    const firstChapter = data?.firstChapter;

    if (manifest) {
      untrack(() => {
        console.log("📚 Initializing store from manifest...");
        chaptersStore.initFromManifest(manifest, basePath);

        // 设置第一章数据
        if (manifest.chapters.length > 0 && firstChapter) {
          chaptersStore.setChapterData(0, {
            textContent: firstChapter.textContent,
            segments: firstChapter.segments.map((seg, idx) => ({
              ...seg,
              globalId: idx,
              globalStart: seg.start,
              globalEnd: seg.end,
              chapterIndex: 0,
            })),
          });
        }

        // 启动全量加载
        chaptersStore.loadAllBookData();
      });
    }
  });

  // 当前播放的全局时间
  let currentGlobalTime = $state(0);

  // TextContent 组件引用
  let textContentRef: any = $state(null);

  // 当前播放的章节索引
  let currentChapterIndex = $state(0);

  // 当前播放章节的音频 src (自动派生)
  let currentAudioSrc = $derived(
    chaptersStore.chapters[currentChapterIndex]?.audioSrc || "",
  );

  // 音频是否正在播放
  let isPlaying = $state(false);

  // AudioPlayer 引用
  let audioPlayerRef: any;

  // onMount
  onMount(() => {
    console.log("✅ Reader page mounted");
  });

  // 处理音频时间更新
  function handleTimeUpdate(chapterTime: number, _globalTime: number) {
    // 计算全局时间
    const chapter = chaptersStore.chapters[currentChapterIndex];
    if (chapter) {
      currentGlobalTime = chapter.globalStartTime + chapterTime;
    }
  }

  // 处理章节结束（自动切换到下一章）
  async function handleChapterEnd() {
    const nextIndex = currentChapterIndex + 1;
    if (nextIndex < chaptersStore.chapters.length) {
      // 数据已由 loadAllBookData 加载，无需手动 load

      // 切换章节索引，currentAudioSrc 会自动更新
      currentChapterIndex = nextIndex;

      // 等待 DOM 更新
      await tick();

      // 关键修复：从 0 秒开始播放下一章节
      // loadAndPlay 只接受一个参数 time，不是 (chapterIndex, time)
      audioPlayerRef?.loadAndPlay(0);
    }
  }

  // 处理文字点击跳转
  async function handleTextSeek(
    globalTime: number,
    targetChapterIndex: number,
  ) {
    console.log("📍 handleTextSeek", {
      globalTime,
      targetChapterIndex,
      currentChapterIndex,
    });

    // 计算章节内时间
    const chapter = chaptersStore.chapters[targetChapterIndex];
    const chapterTime = globalTime - chapter.globalStartTime;

    if (targetChapterIndex !== currentChapterIndex) {
      // 跨章节跳转
      console.log("🔄 跨章节跳转", {
        chapterTime,
        globalStartTime: chapter.globalStartTime,
      });

      // 先设置 pendingGlobalSeek，这样音频加载完成后会自动跳转
      audioPlayerRef?.seekToChapterTime(targetChapterIndex, chapterTime);

      // 切换章节索引，这会触发 currentAudioSrc 更新
      currentChapterIndex = targetChapterIndex;

      // 等待 DOM 更新 src，然后音频会重新加载
      // handleLoadedMetadata 会处理 pendingGlobalSeek 并自动播放
      await tick();
    } else {
      // 同一章节，直接跳转
      console.log("➡️ 同章节跳转", { chapterTime });

      audioPlayerRef?.seekTo(chapterTime);

      // 开始播放
      audioPlayerRef?.play();
    }
  }

  // 处理“跳到朗读处”
  function handleLocate() {
    textContentRef?.scrollToCurrent();
  }

  // --- 主题与字体控制 ---
  let theme = $state("light");
  let fontSize = $state(18);
  let autoScroll = $state(false);

  // 书签
  let bookmarks = $state<BookmarkItem[]>([]);
  let showBookmarksDropdown = $state(false);
  let bookmarksLoading = $state(false);
  let bookmarkMessage = $state("");

  onMount(() => {
    // 初始化主题
    const savedTheme = localStorage.getItem("reader_theme") || "light";
    setTheme(savedTheme);

    // 初始化字体
    const savedSize = localStorage.getItem("reader_font_size");
    if (savedSize) {
      setFontSize(parseInt(savedSize));
    } else {
      setFontSize(18);
    }

    // 恢复上次自动滚动状态
    const savedAutoScroll = localStorage.getItem("reader_auto_scroll");
    if (savedAutoScroll === "true") autoScroll = true;
  });

  function setTheme(t: string) {
    // 只有当主题真正改变时才记录日志 (避免初始化时重复记录)
    if (theme !== t && theme !== "") {
      logActivity("CHANGE_THEME", { from: theme, to: t, book_id: data.bookId });
    }
    theme = t;
    localStorage.setItem("reader_theme", t);
    if (t === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }

  function setFontSize(size: number) {
    const newSize = Math.max(14, Math.min(32, size));

    // 只有当字体大小真正改变时才记录日志
    if (fontSize !== newSize) {
      logActivity("CHANGE_FONT_SIZE", {
        from: fontSize,
        to: newSize,
        book_id: data.bookId,
      });
    }

    fontSize = newSize;
    localStorage.setItem("reader_font_size", String(newSize));
    document.documentElement.style.setProperty(
      "--reader-font-size",
      `${newSize}px`,
    );
  }

  // 自动滚动状态持久化：状态改变时保存到 localStorage
  $effect(() => {
    if (autoScroll !== undefined) {
      localStorage.setItem("reader_auto_scroll", String(autoScroll));
    }
  });

  // 获取选中文字所在 segment 的 globalId，若无选中则用当前播放的 segment
  function getCurrentSegmentGlobalId(): number | null {
    const sel =
      typeof document !== "undefined" ? document.getSelection() : null;
    if (sel && sel.rangeCount > 0) {
      const range = sel.getRangeAt(0);
      if (!range.collapsed) {
        const startNode = range.startContainer;
        const segmentEl = (
          startNode.nodeType === Node.TEXT_NODE
            ? startNode.parentElement
            : startNode
        )?.closest?.(".segment") as HTMLElement | null;
        if (segmentEl) {
          const id = segmentEl.dataset.globalId;
          if (id !== undefined) return parseInt(id, 10);
        }
      }
    }
    const { chapterIndex, chapterTime } =
      chaptersStore.globalToChapterTime(currentGlobalTime);
    const chapter = chaptersStore.chapters[chapterIndex];
    if (!chapter?.segments) return null;
    const seg = chapter.segments.find(
      (s) => chapterTime >= s.start && chapterTime <= s.end,
    );
    return seg?.globalId ?? null;
  }

  function getCurrentSegmentSnippet(): string {
    const id = getCurrentSegmentGlobalId();
    if (id === null) return "";
    const found = chaptersStore.findSegmentByGlobalId(id);
    return found?.segment?.text?.slice(0, 80)?.trim() || "";
  }

  async function loadBookmarks() {
    bookmarksLoading = true;
    try {
      bookmarks = await getBookmarks(data.bookId);
    } catch {
      bookmarks = [];
    } finally {
      bookmarksLoading = false;
    }
  }

  async function handleAddBookmark() {
    const globalId = getCurrentSegmentGlobalId();
    if (globalId === null) {
      bookmarkMessage =
        "请选择文字或播放音频后再添加书签。Please select text or play audio first.";
      return;
    }
    try {
      const snippet = getCurrentSegmentSnippet();
      await createBookmark(data.bookId, {
        segment_index: globalId,
        snippet: snippet || undefined,
      });
      await loadBookmarks();
      bookmarkMessage = "书签已添加 Bookmark added";
      setTimeout(() => (bookmarkMessage = ""), 2000);
    } catch (e) {
      bookmarkMessage = e instanceof Error ? e.message : "添加失败 Failed";
    }
  }

  function openBookmarksDropdown() {
    showBookmarksDropdown = !showBookmarksDropdown;
    if (showBookmarksDropdown) loadBookmarks();
  }

  async function handleGoToBookmark(b: BookmarkItem) {
    showBookmarksDropdown = false;
    const found = chaptersStore.findSegmentByGlobalId(b.segment_index);
    if (found?.segment?.globalStart != null) {
      handleTextSeek(found.segment.globalStart!, found.chapter.index);
    }
    textContentRef?.scrollToSegment(b.segment_index);
  }

  async function handleDeleteBookmark(b: BookmarkItem) {
    try {
      await deleteBookmark(data.bookId, b.id);
      bookmarks = bookmarks.filter((x) => x.id !== b.id);
      bookmarkMessage = "已删除书签 Bookmark removed";
      setTimeout(() => (bookmarkMessage = ""), 2000);
    } catch (e) {
      bookmarkMessage = e instanceof Error ? e.message : "删除失败 Failed";
      setTimeout(() => (bookmarkMessage = ""), 3000);
    }
  }
</script>

<svelte:head>
  <title>{data.bookTitle || "阅读器"} - AudioBook</title>
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1, viewport-fit=cover"
  />
</svelte:head>

<!-- 处理中或失败状态显示 -->
{#if data.processingStatus === "processing" || data.processingStatus === "pending"}
  <div
    class="min-h-screen bg-gradient-to-br from-yellow-50 to-orange-100 flex items-center justify-center"
  >
    <div class="max-w-md w-full mx-4 text-center">
      <div class="bg-white rounded-2xl shadow-xl p-8">
        <div
          class="w-16 h-16 mx-auto mb-4 rounded-full bg-yellow-100 flex items-center justify-center"
        >
          <svg
            class="w-8 h-8 text-yellow-600 animate-spin"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              class="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              stroke-width="4"
            ></circle>
            <path
              class="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
          </svg>
        </div>
        <h1 class="text-xl font-bold text-gray-900 mb-2">
          ⏳ 有声书正在生成中...<br />
          <span class="text-base font-medium">Generating Audiobook...</span>
        </h1>
        <p class="text-gray-600 mb-4 text-sm">
          服务器正在将文本转换为音频，请稍后刷新页面。<br />
          The server is converting text to audio. Please refresh later.
        </p>
        <p class="text-xs text-gray-400 mb-6">
          处理时间取决于文本长度，通常需要几分钟。<br />
          Processing time depends on text length, usually takes a few minutes.
        </p>
        <div class="flex gap-3 justify-center">
          <a
            href="/"
            class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm"
          >
            返回书架 Back
          </a>
          <button
            onclick={() => location.reload()}
            class="px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 transition-colors text-sm"
          >
            刷新页面 Refresh
          </button>
        </div>
      </div>
    </div>
  </div>
{:else if data.processingStatus === "failed" || data.processingStatus === "missing_manifest" || data.processingStatus === "error"}
  <div
    class="min-h-screen bg-gradient-to-br from-red-50 to-pink-100 flex items-center justify-center"
  >
    <div class="max-w-md w-full mx-4 text-center">
      <div class="bg-white rounded-2xl shadow-xl p-8">
        <div
          class="w-16 h-16 mx-auto mb-4 rounded-full bg-red-100 flex items-center justify-center"
        >
          <svg
            class="w-8 h-8 text-red-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </div>
        <h1 class="text-xl font-bold text-gray-900 mb-2">
          ❌ 加载失败 Load Failed
        </h1>
        <p class="text-gray-600 mb-4 text-sm">
          {#if data.processingError}
            {data.processingError}
          {:else}
            转换过程中出现错误，请重新上传或联系管理员。<br />
            Error during conversion. Please re-upload or contact admin.
          {/if}
        </p>
        <p class="text-xs text-gray-500 mb-6">
          如果问题持续存在，请联系网站维护人员。<br />
          If the issue persists, please contact the website administrator.
        </p>
        <a
          href="/"
          class="inline-block px-6 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors text-sm"
        >
          返回书架 Back to Bookshelf
        </a>
      </div>
    </div>
  </div>
{:else}
  <!-- 顶部导航栏 (移除毛玻璃，使用纯色) -->
  <header
    class="fixed top-0 left-0 right-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 z-40 safe-area-top transition-colors duration-300"
  >
    <div
      class="max-w-4xl mx-auto px-4 py-3 flex items-center gap-4 text-gray-900 dark:text-gray-100"
    >
      <!-- 返回按钮 -->
      <a
        href="/"
        class="p-2 -ml-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors touch-manipulation text-gray-600 dark:text-gray-400"
        title="返回书架 Back to Bookshelf"
      >
        <svg
          class="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M15 19l-7-7 7-7"
          />
        </svg>
      </a>

      <!-- 字体控制 (返回按钮右侧) -->
      <div
        class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5"
      >
        <button
          onclick={() => setFontSize(fontSize - 2)}
          class="p-1.5 px-2 text-sm font-medium hover:bg-white dark:hover:bg-gray-700 rounded-md transition-all text-gray-700 dark:text-gray-300"
          title="减小字号 Decrease Font"
        >
          A-
        </button>
        <div class="w-px h-4 bg-gray-300 dark:bg-gray-700 mx-0.5"></div>
        <button
          onclick={() => setFontSize(fontSize + 2)}
          class="p-1.5 px-2 text-sm font-medium hover:bg-white dark:hover:bg-gray-700 rounded-md transition-all text-gray-700 dark:text-gray-300"
          title="增大字号 Increase Font"
        >
          A+
        </button>
      </div>

      <!-- 书签：添加 + 列表 -->
      <div class="relative flex items-center gap-1">
        <button
          onclick={handleAddBookmark}
          class="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-amber-100 dark:hover:bg-amber-900/30 hover:text-amber-600 dark:hover:text-amber-400 transition-colors"
          title="添加书签 Add Bookmark"
        >
          <svg
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"
            />
          </svg>
        </button>
        <button
          onclick={openBookmarksDropdown}
          class="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-blue-100 dark:hover:bg-blue-900/30 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
          title="书签列表 Bookmarks"
        >
          <svg
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
            />
          </svg>
        </button>
        {#if showBookmarksDropdown}
          <div
            class="fixed inset-0 z-40"
            role="button"
            tabindex="-1"
            aria-label="关闭书签列表 Close bookmarks"
            onclick={() => (showBookmarksDropdown = false)}
            onkeydown={(e) => {
              if (e.key === "Escape") showBookmarksDropdown = false;
            }}
          ></div>
          <div
            class="absolute left-0 top-full mt-2 w-72 max-h-64 overflow-y-auto bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg z-50 py-2"
          >
            {#if bookmarksLoading}
              <p class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                加载中... Loading...
              </p>
            {:else if bookmarks.length === 0}
              <p class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                暂无书签 No bookmarks
              </p>
            {:else}
              {#each bookmarks as b}
                <div
                  class="flex items-center gap-1 w-full group border-b border-gray-100 dark:border-gray-700 last:border-0"
                >
                  <button
                    onclick={() => handleGoToBookmark(b)}
                    class="flex-1 min-w-0 px-4 py-2.5 text-left text-sm text-gray-800 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 truncate"
                  >
                    {b.snippet || `段落 ${b.segment_index + 1}`}
                  </button>
                  <button
                    type="button"
                    onclick={(e) => {
                      e.stopPropagation();
                      handleDeleteBookmark(b);
                    }}
                    class="shrink-0 p-2 text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                    title="删除此书签 Delete bookmark"
                    aria-label="删除书签"
                  >
                    <svg
                      class="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      />
                    </svg>
                  </button>
                </div>
              {/each}
            {/if}
          </div>
        {/if}
      </div>
      {#if bookmarkMessage}
        <p
          class="text-xs text-amber-600 dark:text-amber-400 max-w-[8rem] truncate"
          role="status"
        >
          {bookmarkMessage}
        </p>
      {/if}

      <!-- 书名 -->
      <h1 class="text-lg font-medium truncate flex-1 leading-snug text-center">
        {data.bookTitle || "未命名书籍 Untitled"}
      </h1>

      <!-- 主题切换 (进度左侧) -->
      <div
        class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-full p-0.5 relative"
      >
        <!-- 简单的 Toggle Switch 模拟 -->
        <button
          onclick={() => setTheme(theme === "light" ? "dark" : "light")}
          class="relative w-12 h-6 rounded-full transition-colors duration-300 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          style="background-color: {theme === 'light' ? '#e5e7eb' : '#374151'};"
          title="切换主题 Toggle Theme"
          aria-label="Toggle Theme"
        >
          <span
            class="absolute top-0.5 left-0.5 bg-white dark:bg-gray-200 w-5 h-5 rounded-full shadow transform transition-transform duration-300 flex items-center justify-center"
            style="transform: translateX({theme === 'light' ? '0' : '24px'});"
          >
            {#if theme === "light"}
              <svg
                class="w-3 h-3 text-yellow-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                ><path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
                /></svg
              >
            {:else}
              <svg
                class="w-3 h-3 text-indigo-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                ><path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
                /></svg
              >
            {/if}
          </span>
        </button>
      </div>

      <!-- 切换到 EPUB 模式按钮 (暂时隐藏 / Temporary hidden) -->
      <!--
    <a
      href="/epub-reader/{data.bookId}"
      class="px-3 py-1.5 rounded-lg bg-green-100 dark:bg-green-900 hover:bg-green-200 dark:hover:bg-green-800 text-green-800 dark:text-green-200 text-sm font-medium transition-colors"
      title="切换到 EPUB 阅读器 Switch to EPUB"
    >
      📖 EPUB
    </a>
    -->

      <!-- 全书进度：固定宽度 + 导角细框，避免数字变化导致按钮抖动 -->
      <div class="progress-badge">
        {#if chaptersStore.totalDuration > 0}
          {((currentGlobalTime / chaptersStore.totalDuration) * 100).toFixed(
            2,
          )}%
        {:else}
          0.00%
        {/if}
      </div>
    </div>
  </header>

  <!-- 主内容区域 -->
  <!-- 移除 bg-gray-50，改用透明或 inherit (由 body 控制) -->
  <main class="min-h-screen">
    <TextContent
      bind:this={textContentRef}
      {currentGlobalTime}
      {isPlaying}
      {autoScroll}
      onSeekTo={handleTextSeek}
    />
  </main>

  <!-- 音频播放器 -->
  <AudioPlayer
    bind:this={audioPlayerRef}
    audioSrc={currentAudioSrc}
    {currentChapterIndex}
    bind:isPlaying
    bind:autoScroll
    onTimeUpdate={handleTimeUpdate}
    onChapterEnd={handleChapterEnd}
    onLocate={handleLocate}
  />
{/if}

<style>
  /* 安全区域适配 */
  .safe-area-top {
    padding-top: env(safe-area-inset-top, 0);
  }

  /* 触摸优化 */
  .touch-manipulation {
    touch-action: manipulation;
  }

  /* 阅读进度：固定宽度 + 导角超细方框，避免 6.21% → 99.21% 时按钮抖动 */
  .progress-badge {
    width: 5rem;
    min-width: 5rem;
    font-size: 0.875rem;
    font-variant-numeric: tabular-nums;
    color: var(--progress-color, #6b7280);
    text-align: right;
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--progress-border, #e5e7eb);
    border-radius: 6px;
    background: var(--progress-bg, transparent);
    box-sizing: border-box;
  }

  :global(.dark) .progress-badge {
    color: #9ca3af;
    border-color: #4b5563;
  }

  /* 全局背景由 app.css body 控制，这里只移除旧的 override */
  main {
    transition: background 0.3s ease;
  }
</style>
