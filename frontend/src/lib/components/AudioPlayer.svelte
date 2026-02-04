<!--
  音频播放器组件（支持分章节播放）
  
  功能：
  - 播放/暂停按钮
  - 后退 15s / 前进 15s 按钮
  - 倍速选择器
  - 进度条（章节内进度）
  - 章节结束时自动切换到下一章
  - 时间更新传递给父组件
-->
<script lang="ts">
  import { onMount } from "svelte";

  interface Props {
    audioSrc: string;
    currentChapterIndex?: number; // 当前章节索引
    isPlaying?: boolean; // 播放状态（双向绑定）
    onTimeUpdate?: (time: number, globalTime: number) => void;
    onChapterEnd?: () => void;
    onSeekGlobal?: (globalTime: number) => void;
    onLocate?: () => void;
  }

  let {
    audioSrc,
    currentChapterIndex = 0,
    isPlaying = $bindable(false),
    onTimeUpdate,
    onChapterEnd,
    onSeekGlobal,
    onLocate,
  }: Props = $props();

  let audioElement: HTMLAudioElement | null = $state(null);
  // isPlaying 现在是 prop，不需要本地 state 定义 (或者如果是 bindable prop，它就是 state)
  // Let's rely on the bound prop directly.

  let currentTime = $state(0);
  let duration = $state(0);
  let playbackSpeed = $state(1);
  let showSpeedMenu = $state(false);

  // 跨章节跳转引用
  let pendingGlobalSeek: { globalTime: number; chapterIndex: number } | null =
    null;

  const PLAYBACK_SPEEDS = [3, 2.5, 2.25, 2, 1.75, 1.5, 1.25, 1.0, 0.7];

  onMount(() => {
    const savedSpeed = localStorage.getItem("audio_playback_speed");
    if (savedSpeed) {
      playbackSpeed = parseFloat(savedSpeed);
    }
  });

  // 计算进度百分比
  let progress = $derived(duration > 0 ? (currentTime / duration) * 100 : 0);

  // 格式化时间
  function formatTime(seconds: number): string {
    if (!isFinite(seconds) || seconds < 0) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  }

  // 同步音频元素状态
  function handleTimeUpdate() {
    if (audioElement) {
      currentTime = audioElement.currentTime;
      // 报告全局时间（需要从外部获取 globalStartTime）
      onTimeUpdate?.(currentTime, currentTime); // 简化版，page.svelte 会处理
    }
  }

  function handleLoadedMetadata() {
    if (audioElement) {
      duration = audioElement.duration;
      // 恢复播放速度（因为 load() 会重置它）
      audioElement.playbackRate = playbackSpeed;

      // 处理待处理的跨章节跳转
      if (
        pendingGlobalSeek &&
        pendingGlobalSeek.chapterIndex === currentChapterIndex
      ) {
        // 已切换到正确章节，现在跳转到时间（这里的globalTime实际是章节内时间）
        audioElement.currentTime = pendingGlobalSeek.globalTime;
        pendingGlobalSeek = null;

        // 自动开始播放
        audioElement.play().catch((err) => {
          console.error("自动播放失败:", err);
        });
      }
    }
  }

  function handlePlay() {
    isPlaying = true;
  }

  export function loadAndPlay(time: number) {
    if (!audioElement) return;

    // 尝试直接跳转并播放
    // 注意：如果 src 刚改变，浏览器可能会处理加载
    try {
      if (isFinite(time)) {
        audioElement.currentTime = time;
      }
      audioElement.play().catch((e) => console.warn("Play error:", e));
      isPlaying = true;
    } catch (e) {
      console.error("loadAndPlay error:", e);
    }
  }

  function handlePause() {
    isPlaying = false;
  }

  function handleEnded() {
    isPlaying = false;
    onChapterEnd?.();
  }

  // 播放/暂停
  function togglePlay() {
    if (!audioElement) return;

    if (isPlaying) {
      audioElement.pause();
    } else {
      audioElement.play();
    }
  }

  // 后退 15 秒
  function backward15() {
    if (!audioElement) return;
    audioElement.currentTime = Math.max(0, audioElement.currentTime - 15);
  }

  // 前进 15 秒
  function forward15() {
    if (!audioElement) return;
    audioElement.currentTime = Math.min(
      audioElement.duration,
      audioElement.currentTime + 15,
    );
  }

  // 设置播放速度
  function setSpeed(speed: number) {
    playbackSpeed = speed;
    localStorage.setItem("audio_playback_speed", speed.toString());
    if (audioElement) {
      audioElement.playbackRate = speed;
    }
    showSpeedMenu = false;
  }

  // 键盘操作进度条
  function handleProgressKeydown(event: KeyboardEvent) {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      backward15();
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      forward15();
    }
  }

  // 点击进度条跳转
  function handleProgressClick(event: MouseEvent | TouchEvent) {
    if (!audioElement) return;

    const target = event.currentTarget as HTMLElement;
    const rect = target.getBoundingClientRect();

    let clientX: number;
    if ("touches" in event) {
      clientX =
        event.touches[0]?.clientX ?? event.changedTouches[0]?.clientX ?? 0;
    } else {
      clientX = event.clientX;
    }

    const percent = (clientX - rect.left) / rect.width;
    audioElement.currentTime = percent * audioElement.duration;
  }

  // 外部跳转到指定章节内时间
  // 外部跳转（当前章节内）
  export function seekTo(time: number) {
    if (audioElement) {
      audioElement.currentTime = time;
    }
  }

  // 跨章节跳转（由 page.svelte 调用）
  export function seekToChapterTime(chapterIndex: number, chapterTime: number) {
    if (chapterIndex !== currentChapterIndex) {
      // 需要切换章节，保存待处理的跳转
      pendingGlobalSeek = { globalTime: chapterTime, chapterIndex };
      // page.svelte 会切换 audioSrc
    } else {
      // 同一章节，直接跳转
      seekTo(chapterTime);
    }
  }

  // 外部调用开始播放
  export function play() {
    if (audioElement && !isPlaying) {
      audioElement.play().catch((err) => {
        console.error("播放失败:", err);
      });
    }
  }

  // 从指定时间开始播放
  export function playFrom(time: number) {
    if (audioElement) {
      // 先设置时间
      audioElement.currentTime = time;
      // 再尝试播放
      audioElement.play().catch((err) => {
        console.error("播放失败:", err);
      });
    }
  }

  // 外部获取播放状态
  export function getIsPlaying(): boolean {
    return isPlaying;
  }

  export function pause() {
    audioElement?.pause();
  }

  // 键盘快捷键
  function handleKeydown(event: KeyboardEvent) {
    if (
      event.target instanceof HTMLInputElement ||
      event.target instanceof HTMLTextAreaElement
    ) {
      return;
    }

    switch (event.code) {
      case "Space":
        event.preventDefault();
        togglePlay();
        break;
      case "ArrowLeft":
        event.preventDefault();
        backward15();
        break;
      case "ArrowRight":
        event.preventDefault();
        forward15();
        break;
    }
  }

  // 监听 audioSrc 变化
  $effect(() => {
    // 依赖 audioSrc 的变化
    void audioSrc;

    if (audioElement) {
      // 当源改变时，强制重新加载
      // 这会触发 onloadedmetadata，从而处理 pendingGlobalSeek
      audioElement.load();
    }
  });

  // 同步播放速度
  $effect(() => {
    if (audioElement) {
      audioElement.playbackRate = playbackSpeed;
    }
  });
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- 隐藏的音频元素 -->
<audio
  bind:this={audioElement}
  src={audioSrc}
  ontimeupdate={handleTimeUpdate}
  onloadedmetadata={handleLoadedMetadata}
  onplay={handlePlay}
  onpause={handlePause}
  onended={handleEnded}
  preload="metadata"
></audio>

<!-- 播放器 UI -->
<div class="player-container">
  <!-- 进度条 -->
  <div
    class="progress-bar"
    onclick={handleProgressClick}
    ontouchend={handleProgressClick}
    role="slider"
    tabindex="0"
    onkeydown={handleProgressKeydown}
    aria-label="Seek slider"
    aria-valuenow={progress}
    aria-valuemin={0}
    aria-valuemax={100}
  >
    <div class="progress-fill" style="width: {progress}%"></div>
    <div class="progress-thumb" style="left: {progress}%"></div>
  </div>

  <!-- 控制按钮 -->
  <div class="controls">
    <!-- 左侧：当前时间 -->
    <div class="time-display">
      <span class="time-current">{formatTime(currentTime)}</span>
      <span class="time-separator">/</span>
      <span class="time-duration">{formatTime(duration)}</span>
    </div>

    <!-- 中间控制区 -->
    <div class="control-buttons">
      <!-- 后退 15s -->
      <button class="control-btn" onclick={backward15} title="后退 15 秒">
        <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0019 16V8a1 1 0 00-1.6-.8l-5.334 4z"
          />
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M4.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0011 16V8a1 1 0 00-1.6-.8l-5.334 4z"
          />
        </svg>
        <span class="btn-label">15</span>
      </button>

      <!-- 播放/暂停 -->
      <button
        class="play-btn"
        onclick={togglePlay}
        title={isPlaying ? "暂停" : "播放"}
      >
        {#if isPlaying}
          <svg class="icon-lg" fill="currentColor" viewBox="0 0 24 24">
            <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
          </svg>
        {:else}
          <svg class="icon-lg" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z" />
          </svg>
        {/if}
      </button>

      <!-- 前进 15s -->
      <button class="control-btn" onclick={forward15} title="前进 15 秒">
        <span class="btn-label">15</span>
        <svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M11.933 12.8a1 1 0 000-1.6L6.6 7.2A1 1 0 005 8v8a1 1 0 001.6.8l5.333-4z"
          />
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19.933 12.8a1 1 0 000-1.6l-5.333-4A1 1 0 0013 8v8a1 1 0 001.6.8l5.333-4z"
          />
        </svg>
      </button>
    </div>

    <!-- 右侧：Jump and Speed -->
    <div class="speed-container">
      <!-- 跳到朗读处按钮 -->
      <button
        class="speed-btn flex items-center gap-1 !px-3 mr-2 bg-blue-50/50 hover:bg-blue-100 dark:bg-gray-700/50"
        onclick={onLocate}
        title="滚动到当前朗读位置"
      >
        <svg
          class="icon w-3.5 h-3.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
          />
          <!-- Wait that's link icon. I want target icon -->
          <circle cx="12" cy="12" r="3" />
          <path
            d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z"
          />
          <!-- Simple target -->
        </svg>
        <span class="text-xs">跳到朗读处</span>
      </button>

      <button
        class="speed-btn"
        onclick={() => (showSpeedMenu = !showSpeedMenu)}
      >
        {playbackSpeed}x
      </button>

      {#if showSpeedMenu}
        <!-- 速度菜单 -->
        <div class="speed-menu">
          {#each PLAYBACK_SPEEDS as speed}
            <button
              class="speed-option"
              class:active={speed === playbackSpeed}
              onclick={() => setSpeed(speed)}
            >
              {speed}x
            </button>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>

<!-- 点击外部关闭速度菜单 -->
{#if showSpeedMenu}
  <div
    class="overlay"
    role="button"
    tabindex="0"
    aria-label="Close speed menu"
    onclick={() => (showSpeedMenu = false)}
    onkeydown={(e) => {
      if (e.key === "Enter" || e.key === " ") showSpeedMenu = false;
    }}
  ></div>
{/if}

<style>
  .player-container {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    border-top: 1px solid #e5e7eb;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.08);
    z-index: 50;
    padding-bottom: env(safe-area-inset-bottom, 0);
  }

  .progress-bar {
    height: 6px;
    background: #e5e7eb;
    cursor: pointer;
    position: relative;
    touch-action: none;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #3b82f6, #2563eb);
    transition: width 0.1s ease;
  }

  .progress-thumb {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 14px;
    height: 14px;
    background: #2563eb;
    border-radius: 50%;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    opacity: 0;
    transition: opacity 0.2s;
  }

  .progress-bar:hover .progress-thumb,
  .progress-bar:active .progress-thumb {
    opacity: 1;
  }

  .controls {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    gap: 12px;
  }

  .time-display {
    font-size: 13px;
    color: #6b7280;
    min-width: 90px;
    font-variant-numeric: tabular-nums;
  }

  .time-current {
    color: #374151;
    font-weight: 500;
  }

  .time-separator {
    margin: 0 2px;
    color: #9ca3af;
  }

  .time-duration {
    color: #9ca3af;
  }

  .control-buttons {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .control-btn {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 8px 12px;
    border-radius: 9999px;
    background: #f3f4f6;
    color: #374151;
    font-size: 12px;
    font-weight: 500;
    transition: all 0.15s;
    touch-action: manipulation;
  }

  .control-btn:hover {
    background: #e5e7eb;
  }

  .control-btn:active {
    background: #d1d5db;
    transform: scale(0.95);
  }

  .control-btn .icon {
    width: 18px;
    height: 18px;
  }

  .control-btn .btn-label {
    font-size: 11px;
  }

  .play-btn {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: linear-gradient(135deg, #3b82f6, #2563eb);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    transition: all 0.15s;
    touch-action: manipulation;
  }

  .play-btn:hover {
    transform: scale(1.05);
    box-shadow: 0 6px 16px rgba(37, 99, 235, 0.4);
  }

  .play-btn:active {
    transform: scale(0.95);
  }

  .play-btn .icon-lg {
    width: 28px;
    height: 28px;
  }

  .speed-container {
    position: relative;
    min-width: 50px;
    display: flex;
    justify-content: flex-end;
  }

  .speed-btn {
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 600;
    color: #374151;
    background: #f3f4f6;
    border-radius: 9999px;
    transition: all 0.15s;
    touch-action: manipulation;
  }

  .speed-btn:hover {
    background: #e5e7eb;
  }

  .speed-menu {
    position: absolute;
    bottom: calc(100% + 8px);
    right: 0;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
    padding: 4px;
    min-width: 80px;
    max-height: 400px; /* Increase max height to avoid scroll */
    overflow-y: visible; /* No scroll */
  }

  .speed-option {
    width: 100%;
    padding: 8px 16px; /* Decrease padding to fit */
    font-size: 14px;
    text-align: left;
    border-radius: 8px;
    transition: all 0.1s;
  }

  .speed-option:hover {
    background: #f3f4f6;
  }

  .speed-option.active {
    background: #eff6ff;
    color: #2563eb;
    font-weight: 600;
  }

  .overlay {
    position: fixed;
    inset: 0;
    z-index: 40;
  }

  /* 响应式 - 小屏幕 */
  @media (max-width: 480px) {
    .controls {
      padding: 10px 12px;
    }

    .time-display {
      font-size: 12px;
      min-width: 80px;
    }

    .control-btn {
      padding: 6px 10px;
    }

    .control-btn .icon {
      width: 16px;
      height: 16px;
    }

    .play-btn {
      width: 48px;
      height: 48px;
    }

    .play-btn .icon-lg {
      width: 24px;
      height: 24px;
    }

    .speed-btn {
      padding: 5px 10px;
      font-size: 12px;
    }
  }
  /* 暗色模式支持 */
  /* 暗色模式支持 (Manual Class) */
  :global(.dark) .player-container {
    background: #1f2937;
    border-color: #374151;
  }
  :global(.dark) .progress-bar {
    background: #374151;
  }
  :global(.dark) .time-current {
    color: #e5e7eb;
  }
  :global(.dark) .control-btn,
  :global(.dark) .speed-btn {
    background: #374151;
    color: #e5e7eb;
  }
  :global(.dark) .control-btn:hover,
  :global(.dark) .speed-btn:hover {
    background: #4b5563;
  }
  :global(.dark) .speed-menu {
    background: #1f2937;
    border-color: #374151;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
  }
  :global(.dark) .speed-option {
    color: #e5e7eb;
  }
  :global(.dark) .speed-option:hover {
    background: #374151;
  }
  :global(.dark) .speed-option.active {
    background: #172554;
    color: #60a5fa;
  }
</style>
