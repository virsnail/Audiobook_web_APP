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
  });

  function setTheme(t: string) {
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
    fontSize = newSize;
    localStorage.setItem("reader_font_size", String(newSize));
    document.documentElement.style.setProperty(
      "--reader-font-size",
      `${newSize}px`,
    );
  }
</script>

<svelte:head>
  <title>{data.bookTitle || "阅读器"} - AudioBook</title>
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1, viewport-fit=cover"
  />
</svelte:head>

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
      title="返回书架"
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
        title="减小字号"
      >
        A-
      </button>
      <div class="w-px h-4 bg-gray-300 dark:bg-gray-700 mx-0.5"></div>
      <button
        onclick={() => setFontSize(fontSize + 2)}
        class="p-1.5 px-2 text-sm font-medium hover:bg-white dark:hover:bg-gray-700 rounded-md transition-all text-gray-700 dark:text-gray-300"
        title="增大字号"
      >
        A+
      </button>
    </div>

    <!-- 书名 -->
    <h1 class="text-lg font-medium truncate flex-1 leading-snug text-center">
      {data.bookTitle || "未命名书籍"}
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
        title="切换主题"
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

    <!-- 全书进度 -->
    <div
      class="text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap min-w-[3em] text-right"
    >
      {#if chaptersStore.totalDuration > 0}
        {Math.floor((currentGlobalTime / chaptersStore.totalDuration) * 100)}%
      {:else}
        0%
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
    onSeekTo={handleTextSeek}
  />
</main>

<!-- 音频播放器 -->
<AudioPlayer
  bind:this={audioPlayerRef}
  audioSrc={currentAudioSrc}
  {currentChapterIndex}
  onTimeUpdate={handleTimeUpdate}
  onChapterEnd={handleChapterEnd}
  onLocate={handleLocate}
/>

<style>
  /* 安全区域适配 */
  .safe-area-top {
    padding-top: env(safe-area-inset-top, 0);
  }

  /* 触摸优化 */
  .touch-manipulation {
    touch-action: manipulation;
  }

  /* 全局背景由 app.css body 控制，这里只移除旧的 override */
  main {
    transition: background 0.3s ease;
  }
</style>
