<script lang="ts">
  import { resolve } from "$app/paths";
  /**
   * EPUB Reader Page (方案2专用)
   *
   * 独立于TXT阅读器的EPUB阅读器页面
   * 加载EPUB HTML章节 + 音频对齐数据
   * 实现点击文字跳转音频功能
   */

  import { onMount, tick, untrack } from "svelte";
  import AudioPlayerEpub from "$lib/components/AudioPlayerEpub.svelte";
  import EpubContent from "$lib/components/EpubContent.svelte";
  import { epubChaptersStore } from "$lib/stores/epub-chapters.svelte";

  interface PageData {
    bookId: string;
    book: any;
    epubManifest: any;
  }

  let { data }: { data: PageData } = $props();

  // 当前播放的全局时间
  let currentGlobalTime = $state(0);

  // EPUB内容组件引用
  let epubContentRef: any = $state(null);

  // 当前播放的章节索引
  let currentChapterIndex = $state(0);

  // 当前播放章节的音频 src (自动派生)
  let currentAudioSrc = $derived(
    epubChaptersStore.chapters[currentChapterIndex]?.audioSrc || "",
  );

  // 音频是否正在播放
  let isPlaying = $state(false);

  // AudioPlayer 引用
  let audioPlayerRef: any;

  // 初始化EPUB数据
  $effect(() => {
    const manifest = data?.epubManifest;
    const bookId = data?.bookId;

    untrack(() => {
      if (manifest && bookId && bookId !== epubChaptersStore.bookId) {
        console.log("📚 [EPUB Page] Initializing EPUB store from manifest...");
        epubChaptersStore.initFromManifest(manifest, bookId);

        // 启动全量加载
        console.log("📥 [EPUB Page] Starting full book data load...");
        epubChaptersStore.loadAllBookData();
      }
    });
  });

  onMount(() => {
    console.log("✅ [EPUB Page] EPUB Reader page mounted");
    console.log("📖 [EPUB Page] Book data:", data.book);
    console.log("📋 [EPUB Page] EPUB manifest:", data.epubManifest);
  });

  // 处理音频时间更新
  function handleTimeUpdate(chapterTime: number, _globalTime: number) {
    // 计算全局时间
    const chapter = epubChaptersStore.chapters[currentChapterIndex];
    if (chapter) {
      currentGlobalTime = chapter.globalStartTime + chapterTime;
    }
  }

  // 处理章节结束（自动切换到下一章）
  async function handleChapterEnd() {
    console.log("⏭️ [EPUB Page] Chapter ended, switching to next...");
    const nextIndex = currentChapterIndex + 1;
    if (nextIndex < epubChaptersStore.chapters.length) {
      currentChapterIndex = nextIndex;
      console.log(`📍 [EPUB Page] Switched to chapter ${nextIndex}`);
      await tick();
      audioPlayerRef?.loadAndPlay(0);
    } else {
      console.log("🏁 [EPUB Page] Reached end of book");
    }
  }

  // 处理文字点击跳转
  async function handleTextSeek(
    globalTime: number,
    targetChapterIndex: number,
  ) {
    console.log("🖱️ [EPUB Page] Text clicked - seeking to:", {
      globalTime,
      targetChapterIndex,
      currentChapterIndex,
    });

    const chapter = epubChaptersStore.chapters[targetChapterIndex];
    const chapterTime = globalTime - chapter.globalStartTime;

    console.log(`⏰ [EPUB Page] Chapter time: ${chapterTime.toFixed(2)}s`);

    if (targetChapterIndex !== currentChapterIndex) {
      // 跨章节跳转
      console.log("🔀 [EPUB Page] Cross-chapter seek");
      audioPlayerRef?.seekToChapterTime(targetChapterIndex, chapterTime);
      currentChapterIndex = targetChapterIndex;
      await tick();
    } else {
      // 同一章节，直接跳转
      console.log("▶️ [EPUB Page] Same chapter seek");
      audioPlayerRef?.seekTo(chapterTime);
      audioPlayerRef?.play();
    }
  }

  // 处理"跳到朗读处"
  function handleLocate() {
    console.log("🎯 [EPUB Page] Locate current reading position");
    epubContentRef?.scrollToCurrent();
  }

  // 主题与字体控制
  let theme = $state("light");
  let fontSize = $state(18);

  onMount(() => {
    // 初始化主题
    const savedTheme = localStorage.getItem("reader_theme") || "light";
    console.log(`🎨 [EPUB Page] Loading theme: ${savedTheme}`);
    setTheme(savedTheme);

    // 初始化字体
    const savedSize = localStorage.getItem("reader_font_size");
    if (savedSize) {
      console.log(`🔤 [EPUB Page] Loading font size: ${savedSize}px`);
      setFontSize(parseInt(savedSize));
    } else {
      setFontSize(18);
    }
  });

  function setTheme(t: string) {
    console.log(`🎨 [EPUB Page] Setting theme to: ${t}`);
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
    console.log(`🔤 [EPUB Page] Setting font size to: ${newSize}px`);
    fontSize = newSize;
    localStorage.setItem("reader_font_size", String(newSize));
    document.documentElement.style.setProperty(
      "--reader-font-size",
      `${newSize}px`,
    );
  }
</script>

<div class="epub-reader-container min-h-screen bg-gray-50 dark:bg-gray-900">
  <!-- 顶部控制栏 -->
  <div
    class="sticky top-0 z-10 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm"
  >
    <div class="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
      <!-- 左侧：返回 + 书名 + 字体控制 -->
      <div class="flex items-center gap-4">
        <!-- 返回按钮 -->
        <a
          href={resolve('/')}
          class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          title="返回书架"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M10 19l-7-7m0 0l7-7m-7 7h18"
            />
          </svg>
        </a>

        <!-- 书名 -->
        <h1
          class="text-lg font-bold text-gray-800 dark:text-gray-100 truncate max-w-[12rem] sm:max-w-md hidden sm:block"
        >
          {data.book.title}
        </h1>

        <!-- 字体控制 (与 TXT 阅读器保持一致) -->
        <div
          class="flex items-center bg-gray-100 dark:bg-gray-700 rounded-lg p-1"
        >
          <button
            class="px-3 py-1 text-sm font-medium hover:bg-white dark:hover:bg-gray-600 rounded"
            onclick={() => setFontSize(fontSize - 2)}
          >
            A-
          </button>
          <span class="px-2 text-xs text-gray-500 dark:text-gray-400"
            >{fontSize}px</span
          >
          <button
            class="px-3 py-1 text-sm font-medium hover:bg-white dark:hover:bg-gray-600 rounded"
            onclick={() => setFontSize(fontSize + 2)}
          >
            A+
          </button>
        </div>
      </div>

      <!-- 右侧：模式切换 + 进度 -->
      <div class="flex items-center gap-3">
        <!-- EPUB/TXT 切换 -->
        <div class="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
          <a
            href={resolve('/reader/[bookId]', { bookId: data.bookId })}
            class="px-3 py-1 text-sm font-medium rounded text-gray-500 hover:text-gray-700 dark:text-gray-400"
            title="切换到 TXT 模式"
          >
            TXT
          </a>
          <button
            class="px-3 py-1 text-sm font-medium rounded bg-white dark:bg-gray-600 shadow-sm text-blue-600 dark:text-blue-400"
            disabled
          >
            EPUB
          </button>
        </div>

        <!-- 主题切换 (Toggle Switch 样式) -->
        <button
          onclick={() => setTheme(theme === "light" ? "dark" : "light")}
          class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          class:bg-gray-200={theme === "light"}
          class:bg-blue-600={theme === "dark"}
        >
          <span
            class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
            class:translate-x-1={theme === "light"}
            class:translate-x-6={theme === "dark"}
          ></span>
        </button>

        <!-- 进度 -->
        <div
          class="text-xs text-gray-500 dark:text-gray-400 font-mono w-[3ch] text-right"
        >
          {#if epubChaptersStore.totalDuration > 0}
            {Math.floor(
              (currentGlobalTime / epubChaptersStore.totalDuration) * 100,
            )}%
          {:else}
            0%
          {/if}
        </div>
      </div>
    </div>
  </div>

  <!-- EPUB内容区域 -->
  <div class="max-w-4xl mx-auto px-4 py-6">
    <EpubContent
      bind:this={epubContentRef}
      bookId={data.bookId}
      {currentChapterIndex}
      {currentGlobalTime}
      {isPlaying}
      onTextSeek={handleTextSeek}
    />
  </div>

  <!-- 音频播放器 -->
  <div class="fixed bottom-0 left-0 right-0 z-20">
    <AudioPlayerEpub
      bind:this={audioPlayerRef}
      audioSrc={currentAudioSrc}
      chapterIndex={currentChapterIndex}
      onTimeUpdate={handleTimeUpdate}
      onChapterEnd={handleChapterEnd}
      onPlayingChange={(playing) => {
        isPlaying = playing;
      }}
    />
  </div>
</div>

<style>
  :global(:root) {
    --reader-font-size: 18px;
  }
</style>
