/**
 * 章节状态管理 Store（懒加载版）
 * 
 * 功能：
 * - 初始化时仅从 manifest 创建章节骨架（不加载任何数据）
 * - 按需加载单个章节的文本+对齐数据
 * - 自动卸载远离当前视口的章节数据以释放内存
 * - globalId 使用确定性策略: chapterIndex * 100000 + localSegmentIndex
 *   这样无论加载/卸载顺序如何，ID 都是稳定唯一的
 */

import { authStore } from '$lib/stores/auth.svelte.ts';
import type { Chapter, ChapterMeta, BookManifest, Segment, ChapterLoadState } from '$lib/types/chapter';

// ========== 常量 ==========
// 每个章节的 globalId 偏移量（单个章节最多 100000 个 segment）
const GLOBAL_ID_MULTIPLIER = 100_000;

// 章节加载状态 Map
const chapterLoadStates = $state<Map<number, ChapterLoadState>>(new Map());

// 所有章节数据
let chapters = $state<Chapter[]>([]);

// 当前播放的章节索引
let currentChapterIndex = $state(0);

// 全书总时长
let totalDuration = $state(0);

// 基础 URL
let baseUrl = $state('/sample');

/**
 * 根据 chapterIndex 和 localSegmentIndex 计算确定性 globalId
 * 公式: chapterIndex * 100000 + localSegmentIndex
 * 这样无论章节以什么顺序加载/卸载，ID 始终一致
 */
function computeGlobalId(chapterIndex: number, localSegmentIndex: number): number {
  return chapterIndex * GLOBAL_ID_MULTIPLIER + localSegmentIndex;
}

/**
 * 设置章节数据（触发响应式更新）
 */
function setChapterData(index: number, updates: Partial<Chapter>): void {
  if (index < 0 || index >= chapters.length) return;
  
  // 创建新对象触发响应式
  const updated = { ...chapters[index], ...updates };
  
  // 创建新数组
  chapters = [
    ...chapters.slice(0, index),
    updated,
    ...chapters.slice(index + 1)
  ];
}

/**
 * 从 manifest 初始化章节骨架（不加载任何文本/对齐数据）
 */
function initFromManifest(manifest: BookManifest, basePath: string = '/sample') {
  // 防止重复初始化
  if (baseUrl === basePath && chapters.length === manifest.chapters.length) {
    console.log('📚 Store already initialized for', basePath);
    return;
  }

  baseUrl = basePath;
  totalDuration = manifest.totalDuration;
  console.log('📚 initFromManifest', { 
    totalDuration, 
    chaptersCount: manifest.chapters.length,
    manifestTotalDuration: manifest.totalDuration 
  });
  
  let globalTime = 0;
  chapters.length = 0; // Clear array
  
  const newChapters: Chapter[] = [];
  chapterLoadStates.clear();
  
  manifest.chapters.forEach((meta, index) => {
    newChapters.push({
      ...meta,
      index,
      audioSrc: `${basePath}/chapters/${meta.id}/audio?token=${authStore.token || ''}`,
      globalStartTime: globalTime,
      textContent: undefined,  // 懒加载
      segments: undefined,     // 懒加载
    });
    globalTime += meta.duration;
    
    chapterLoadStates.set(index, {
      textLoaded: false,
      dataLoaded: false,
      isVisible: false,
      state: 'idle',
    });
  });
  
  chapters = newChapters;
}

/**
 * 加载单个章节的文本+对齐数据
 * 如果已加载或正在加载，直接返回
 */
async function loadChapterData(index: number): Promise<boolean> {
  if (index < 0 || index >= chapters.length) return false;
  
  const state = chapterLoadStates.get(index);
  if (state?.dataLoaded || state?.state === 'loading') return true;
  
  if (state) state.state = 'loading';
  
  const chapter = chapters[index];
  const headers = authStore.getAuthHeader();
  
  try {
    console.log(`📡 [懒加载] 加载章节 ${index}: ${chapter.id}`);
    
    const [textRes, alignRes] = await Promise.all([
      fetch(`${baseUrl}/chapters/${chapter.id}/text`, { headers }),
      fetch(`${baseUrl}/chapters/${chapter.id}/alignment`, { headers }),
    ]);
    
    if (!textRes.ok || !alignRes.ok) {
      console.warn(`❌ 加载章节 ${index} 失败: text=${textRes.status}, align=${alignRes.status}`);
      setChapterData(index, { textContent: "加载失败: 无法获取章节内容" });
      if (state) state.state = 'error';
      return false;
    }
    
    const textContent = await textRes.text();
    const rawSegments: Segment[] = await alignRes.json();
    
    // 使用确定性 globalId 分配策略
    const segments = rawSegments.map((seg, localIdx) => ({
      ...seg,
      globalId: computeGlobalId(index, localIdx),
      globalStart: chapter.globalStartTime + seg.start,
      globalEnd: chapter.globalStartTime + seg.end,
      chapterIndex: index,
    }));
    
    setChapterData(index, { textContent, segments });
    
    if (state) {
      state.dataLoaded = true;
      state.textLoaded = true;
      state.state = 'loaded';
    }
    
    console.log(`✅ 章节 ${index} 加载完成, ${segments.length} segments`);
    return true;
  } catch (e) {
    console.error(`❌ 加载章节 ${index} 异常:`, e);
    setChapterData(index, { textContent: "加载失败: 网络错误或服务器异常" });
    if (state) state.state = 'error';
    return false;
  }
}

/**
 * 卸载章节数据以释放内存
 * 清除 textContent 和 segments，状态重置为 idle
 */
function unloadChapterData(index: number): void {
  if (index < 0 || index >= chapters.length) return;
  
  const state = chapterLoadStates.get(index);
  if (!state?.dataLoaded) return; // 未加载，无需卸载
  
  console.log(`🗑️ 卸载章节 ${index} 数据`);
  
  setChapterData(index, {
    textContent: undefined,
    segments: undefined,
  });
  
  if (state) {
    state.dataLoaded = false;
    state.textLoaded = false;
    state.state = 'idle';
  }
}

/**
 * 批量确保多个章节已加载
 * 返回 true 当所有请求的章节都成功加载
 */
async function ensureChaptersLoaded(indices: number[]): Promise<boolean> {
  const toLoad = indices.filter(i => {
    if (i < 0 || i >= chapters.length) return false;
    const state = chapterLoadStates.get(i);
    return !state?.dataLoaded && state?.state !== 'loading';
  });
  
  if (toLoad.length === 0) return true;
  
  console.log(`📡 [批量加载] 章节: ${toLoad.join(', ')}`);
  const results = await Promise.all(toLoad.map(i => loadChapterData(i)));
  return results.every(r => r);
}

/**
 * 根据当前可见章节，执行智能加载/卸载
 * 规则：
 * - 可见章节的前 1 个、后 2 个保持加载（预加载窗口）
 * - 超出预加载窗口的章节自动卸载
 */
function updateLoadWindow(visibleIndices: number[]): void {
  if (visibleIndices.length === 0) return;
  
  const minVisible = Math.min(...visibleIndices);
  const maxVisible = Math.max(...visibleIndices);
  
  // 预加载窗口：向前 1 章，向后 2 章
  const keepMin = Math.max(0, minVisible - 1);
  const keepMax = Math.min(chapters.length - 1, maxVisible + 2);
  
  // 加载窗口内的章节
  const toLoad: number[] = [];
  for (let i = keepMin; i <= keepMax; i++) {
    const state = chapterLoadStates.get(i);
    if (!state?.dataLoaded && state?.state !== 'loading') {
      toLoad.push(i);
    }
  }
  
  if (toLoad.length > 0) {
    ensureChaptersLoaded(toLoad);
  }
  
  // 卸载超出窗口的章节
  for (let i = 0; i < chapters.length; i++) {
    if (i < keepMin || i > keepMax) {
      const state = chapterLoadStates.get(i);
      if (state?.dataLoaded) {
        unloadChapterData(i);
      }
    }
  }
}

/**
 * 更新章节可见性
 */
function setChapterVisibility(index: number, isVisible: boolean): void {
  const state = chapterLoadStates.get(index);
  if (state) {
    state.isVisible = isVisible;
  }
}

// ----------------------------------------------------------------------
// 辅助计算函数
// ----------------------------------------------------------------------

function getChapterIndexByGlobalTime(globalTime: number): number {
  for (let i = chapters.length - 1; i >= 0; i--) {
    if (globalTime >= chapters[i].globalStartTime) {
      return i;
    }
  }
  return 0;
}

function globalToChapterTime(globalTime: number): { chapterIndex: number; chapterTime: number } {
  const chapterIndex = getChapterIndexByGlobalTime(globalTime);
  const chapter = chapters[chapterIndex];
  if (!chapter) return { chapterIndex: 0, chapterTime: 0 };
  const chapterTime = globalTime - chapter.globalStartTime;
  return { chapterIndex, chapterTime };
}

function chapterToGlobalTime(chapterIndex: number, chapterTime: number): number {
  if (chapterIndex < 0 || chapterIndex >= chapters.length) return 0;
  return chapters[chapterIndex].globalStartTime + chapterTime;
}

function findSegmentByGlobalId(globalId: number): { chapter: Chapter; segment: Segment } | null {
  for (const chapter of chapters) {
    if (!chapter.segments) continue;
    const segment = chapter.segments.find(s => s.globalId === globalId);
    if (segment) {
      return { chapter, segment };
    }
  }
  return null;
}

function getLoadedChapters(): Chapter[] {
  return chapters.filter((_, index) => {
    const state = chapterLoadStates.get(index);
    return state?.dataLoaded;
  });
}

// ----------------------------------------------------------------------
// 导出 Store
// ----------------------------------------------------------------------

export const chaptersStore = {
  // State getters
  get chapters() { return chapters; },
  get currentChapterIndex() { return currentChapterIndex; },
  set currentChapterIndex(v) { currentChapterIndex = v; },
  get totalDuration() { return totalDuration; },
  get chapterLoadStates() { return chapterLoadStates; },

  // Methods
  initFromManifest,
  loadChapterData,
  unloadChapterData,
  ensureChaptersLoaded,
  updateLoadWindow,
  setChapterVisibility,
  setChapterData,
  
  // Helpers
  getChapterIndexByGlobalTime,
  globalToChapterTime,
  chapterToGlobalTime,
  findSegmentByGlobalId,
  getLoadedChapters,
  computeGlobalId,
};
