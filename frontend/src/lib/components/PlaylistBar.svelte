<!--
  播放列表控制条
  
  显示在 AudioPlayer 上方，用于跨书播放控制：
  - 显示播放列表中的书名列表
  - 当前播放的书高亮
  - 上一本/下一本按钮
  - 点击书名跳转
-->
<script lang="ts">
  import { playlistStore } from "$lib/stores/playlistStore.svelte.ts";

  interface Props {
    bookTitles: Record<string, string>; // {bookId: title}
    onSwitchBook?: (bookId: string, index: number) => void;
  }

  let { bookTitles, onSwitchBook }: Props = $props();

  let scrollContainer: HTMLDivElement | null = $state(null);

  // 自动滚动到当前书籍
  $effect(() => {
    const idx = playlistStore.currentIndex;
    if (scrollContainer) {
      const items = scrollContainer.querySelectorAll('.playlist-item');
      const current = items[idx] as HTMLElement | undefined;
      if (current) {
        current.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
      }
    }
  });

  function handlePrev() {
    const bookId = playlistStore.prevBook();
    if (bookId) {
      onSwitchBook?.(bookId, playlistStore.currentIndex);
    }
  }

  function handleNext() {
    const bookId = playlistStore.nextBook();
    if (bookId) {
      onSwitchBook?.(bookId, playlistStore.currentIndex);
    }
  }

  function handleJumpTo(index: number) {
    const bookId = playlistStore.jumpTo(index);
    if (bookId) {
      onSwitchBook?.(bookId, index);
    }
  }
</script>

{#if playlistStore.isPlaylistMode}
  <div class="playlist-bar">
    <div class="playlist-header">
      <div class="playlist-info">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M4 6h16M4 10h16M4 14h16M4 18h16" />
        </svg>
        <span class="playlist-label">
          播放列表 Playlist ({playlistStore.currentIndex + 1}/{playlistStore.totalBooks})
        </span>
      </div>

      <div class="playlist-nav">
        <button
          class="nav-btn"
          disabled={!playlistStore.hasPrev}
          onclick={handlePrev}
          title="上一本 Previous"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <button
          class="nav-btn"
          disabled={!playlistStore.hasNext}
          onclick={handleNext}
          title="下一本 Next"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>

    <div class="playlist-scroll" bind:this={scrollContainer}>
      {#each playlistStore.bookIds as bookId, i}
        <button
          class="playlist-item"
          class:active={i === playlistStore.currentIndex}
          class:played={i < playlistStore.currentIndex}
          onclick={() => handleJumpTo(i)}
          title={bookTitles[bookId] || bookId}
        >
          <span class="item-index">{i + 1}</span>
          <span class="item-title">{bookTitles[bookId] || `Book ${i + 1}`}</span>
          {#if i === playlistStore.currentIndex}
            <span class="playing-indicator">
              <span class="bar"></span>
              <span class="bar"></span>
              <span class="bar"></span>
            </span>
          {/if}
        </button>
        {#if i < playlistStore.bookIds.length - 1}
          <span class="item-separator">→</span>
        {/if}
      {/each}
    </div>
  </div>
{/if}

<style>
  .playlist-bar {
    position: fixed;
    bottom: 80px; /* above AudioPlayer */
    left: 0;
    right: 0;
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(12px);
    border-top: 1px solid #e5e7eb;
    z-index: 49;
    padding: 6px 12px;
    padding-bottom: calc(6px + env(safe-area-inset-bottom, 0px));
  }

  :global(.dark) .playlist-bar {
    background: rgba(17, 24, 39, 0.92);
    border-top-color: #374151;
  }

  .playlist-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 4px;
  }

  .playlist-info {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #6b7280;
    font-size: 12px;
  }

  :global(.dark) .playlist-info {
    color: #9ca3af;
  }

  .playlist-label {
    font-weight: 500;
  }

  .playlist-nav {
    display: flex;
    gap: 4px;
  }

  .nav-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 6px;
    border: none;
    background: #f3f4f6;
    color: #374151;
    cursor: pointer;
    transition: all 0.15s;
  }

  .nav-btn:hover:not(:disabled) {
    background: #e5e7eb;
  }

  .nav-btn:disabled {
    opacity: 0.3;
    cursor: default;
  }

  :global(.dark) .nav-btn {
    background: #374151;
    color: #e5e7eb;
  }

  :global(.dark) .nav-btn:hover:not(:disabled) {
    background: #4b5563;
  }

  .playlist-scroll {
    display: flex;
    align-items: center;
    gap: 2px;
    overflow-x: auto;
    scroll-behavior: smooth;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    padding: 2px 0;
  }

  .playlist-scroll::-webkit-scrollbar {
    display: none;
  }

  .playlist-item {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    border-radius: 8px;
    border: none;
    background: #f3f4f6;
    color: #6b7280;
    font-size: 12px;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s;
    flex-shrink: 0;
  }

  .playlist-item:hover {
    background: #e5e7eb;
    color: #374151;
  }

  .playlist-item.active {
    background: linear-gradient(135deg, #3b82f6, #2563eb);
    color: white;
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
  }

  .playlist-item.played {
    background: #dbeafe;
    color: #3b82f6;
  }

  :global(.dark) .playlist-item {
    background: #374151;
    color: #9ca3af;
  }

  :global(.dark) .playlist-item:hover {
    background: #4b5563;
    color: #e5e7eb;
  }

  :global(.dark) .playlist-item.active {
    background: linear-gradient(135deg, #3b82f6, #2563eb);
    color: white;
  }

  :global(.dark) .playlist-item.played {
    background: #1e3a5f;
    color: #93c5fd;
  }

  .item-index {
    font-size: 10px;
    opacity: 0.7;
    font-weight: 600;
  }

  .item-title {
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .item-separator {
    color: #d1d5db;
    font-size: 10px;
    flex-shrink: 0;
    margin: 0 1px;
  }

  :global(.dark) .item-separator {
    color: #4b5563;
  }

  /* Playing animation */
  .playing-indicator {
    display: flex;
    align-items: flex-end;
    gap: 1px;
    height: 12px;
    margin-left: 4px;
  }

  .playing-indicator .bar {
    width: 2px;
    background: currentColor;
    border-radius: 1px;
    animation: equalizer 0.8s ease-in-out infinite alternate;
  }

  .playing-indicator .bar:nth-child(1) {
    height: 4px;
    animation-delay: 0s;
  }

  .playing-indicator .bar:nth-child(2) {
    height: 8px;
    animation-delay: 0.2s;
  }

  .playing-indicator .bar:nth-child(3) {
    height: 6px;
    animation-delay: 0.4s;
  }

  @keyframes equalizer {
    0% { height: 4px; }
    100% { height: 12px; }
  }
</style>
