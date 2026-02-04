/**
 * 章节状态管理 Store（重构版）
 * 
 * 功能：
 * - 初始化时一次性加载所有章节数据（文本+对齐）
 * - 简化音频管理（按需播放，可选预加载）
 * - 消除按需加载数据的异步等待
 */

import { authStore } from '$lib/stores/auth.svelte';
import type { Chapter, ChapterMeta, BookManifest, Segment, ChapterLoadState } from '$lib/types/chapter';

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

// 全局 segment 计数器
let globalSegmentCounter = 0;

/**
 * 设置章节数据（触发响应式更新）
 * 用于内部更新
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
 * 从 manifest 初始化章节数据
 */
function initFromManifest(manifest: BookManifest, basePath: string = '/sample') {
  // 防止重复初始化
  if (baseUrl === basePath && chapters.length === manifest.chapters.length) {
    console.log('📚 Store already initialized for', basePath);
    return;
  }

  baseUrl = basePath;
  totalDuration = manifest.totalDuration;
  globalSegmentCounter = 0;
  
  let globalTime = 0;
  chapters.length = 0; // Clear array
  
  const newChapters: Chapter[] = [];
  chapterLoadStates.clear();
  
  manifest.chapters.forEach((meta, index) => {
    newChapters.push({
      ...meta,
      index,
      // Update to API endpoint AND include token for audio playback
      audioSrc: `${basePath}/chapters/${meta.id}/audio?token=${authStore.token || ''}`,
      globalStartTime: globalTime,
      textContent: undefined,
      segments: undefined,
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
 * 加载所有章节的数据（文本和对齐信息）
 * 在应用初始化时一次性调用
 */
async function loadAllBookData(): Promise<void> {
  console.log('📚 Starting to load ALL book data...');
  
  // 自定义并发限制
  const CONCURRENCY_LIMIT = 5;
  const queue = [...chapters]; // Create a copy to process
  
  const headers = authStore.getAuthHeader();

  // 处理单个章节
  const processChapter = async (chapter: Chapter) => {
    const index = chapter.index;
    const state = chapterLoadStates.get(index);
    if (state?.dataLoaded || state?.state === 'loading') return null;

    if (state) state.state = 'loading';

    try {
      console.log(`📡 Fetching text from: ${baseUrl}/chapters/${chapter.id}/text`);
      console.log(`📡 Auth header:`, headers);
      
      const [textRes, alignRes] = await Promise.all([
        fetch(`${baseUrl}/chapters/${chapter.id}/text`, { headers }), // Update to API endpoint with headers
        fetch(`${baseUrl}/chapters/${chapter.id}/alignment`, { headers }), // Update to API endpoint with headers
      ]);

      console.log(`📡 Text response: ${textRes.status} ${textRes.statusText}`);
      console.log(`📡 Align response: ${alignRes.status} ${alignRes.statusText}`);

      if (!textRes.ok || !alignRes.ok) {
         console.warn(`Failed to load parts for chapter ${index}`);
         setChapterData(index, { textContent: "加载失败: 无法获取章节内容" });
         if (state) state.state = 'error';
         return null;
      }

      const textContent = await textRes.text();
      const rawSegments: Segment[] = await alignRes.json();
      
      return { index, textContent, rawSegments };
    } catch (e) {
      console.error(`Error loading chapter ${index}`, e);
      setChapterData(index, { textContent: "加载失败: 网络错误或服务器异常" });
      if (state) state.state = 'error';
      return null;
    }
  };

  // 分批处理
  const results: any[] = [];
  for (let i = 0; i < chapters.length; i += CONCURRENCY_LIMIT) {
    const chunk = chapters.slice(i, i + CONCURRENCY_LIMIT);
    console.log(`📡 Loading chunk ${i / CONCURRENCY_LIMIT + 1}...`);
    const chunkResults = await Promise.all(chunk.map(processChapter));
    results.push(...chunkResults);
  }

  // 按顺序处理数据，分配全局 ID
  globalSegmentCounter = 0; // 重置
  
  results.forEach((res, i) => {
    if (!res) {
        // 如果数据缺失，潜在问题
        return; 
    }

    const segments = res.rawSegments.map((seg: any) => ({
        ...seg,
        globalId: globalSegmentCounter++,
        globalStart: chapters[res.index].globalStartTime + seg.start,
        globalEnd: chapters[res.index].globalStartTime + seg.end,
        chapterIndex: res.index
    }));

    setChapterData(res.index, { 
        textContent: res.textContent, 
        segments 
    });
    
    const state = chapterLoadStates.get(res.index);
    if (state) {
        state.dataLoaded = true;
        state.textLoaded = true;
        state.state = 'loaded';
    }
  });

  console.log('✅ All book data loaded!', { totalSegments: globalSegmentCounter });
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
  // 安全检查
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
  loadAllBookData,
  setChapterVisibility,
  setChapterData,  // Export for first chapter initialization
  
  // Helpers
  getChapterIndexByGlobalTime,
  globalToChapterTime,
  chapterToGlobalTime,
  findSegmentByGlobalId,
  getLoadedChapters,
};
