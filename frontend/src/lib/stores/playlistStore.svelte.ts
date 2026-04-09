/**
 * 播放列表状态管理
 * 
 * 管理跨书播放列表：
 * - 存储要播放的 book ID 列表
 * - 跟踪当前播放到第几本
 * - 提供 next/prev/jumpTo 方法
 */

let playlistBookIds = $state<string[]>([]);
let currentPlaylistIndex = $state(0);
let isPlaylistMode = $state(false);

function setPlaylist(bookIds: string[]) {
  playlistBookIds = bookIds;
  currentPlaylistIndex = 0;
  isPlaylistMode = bookIds.length > 1;
}

function clearPlaylist() {
  playlistBookIds = [];
  currentPlaylistIndex = 0;
  isPlaylistMode = false;
}

function nextBook(): string | null {
  if (currentPlaylistIndex + 1 < playlistBookIds.length) {
    currentPlaylistIndex++;
    return playlistBookIds[currentPlaylistIndex];
  }
  return null; // 已经是最后一本
}

function prevBook(): string | null {
  if (currentPlaylistIndex > 0) {
    currentPlaylistIndex--;
    return playlistBookIds[currentPlaylistIndex];
  }
  return null; // 已经是第一本
}

function jumpTo(index: number): string | null {
  if (index >= 0 && index < playlistBookIds.length) {
    currentPlaylistIndex = index;
    return playlistBookIds[index];
  }
  return null;
}

function getCurrentBookId(): string | null {
  return playlistBookIds[currentPlaylistIndex] || null;
}

function setCurrentByBookId(bookId: string): boolean {
  const idx = playlistBookIds.indexOf(bookId);
  if (idx >= 0) {
    currentPlaylistIndex = idx;
    return true;
  }
  return false;
}

export const playlistStore = {
  get bookIds() { return playlistBookIds; },
  get currentIndex() { return currentPlaylistIndex; },
  get isPlaylistMode() { return isPlaylistMode; },
  get totalBooks() { return playlistBookIds.length; },
  get currentBookId() { return getCurrentBookId(); },
  get hasNext() { return currentPlaylistIndex + 1 < playlistBookIds.length; },
  get hasPrev() { return currentPlaylistIndex > 0; },

  setPlaylist,
  clearPlaylist,
  nextBook,
  prevBook,
  jumpTo,
  getCurrentBookId,
  setCurrentByBookId,
};
