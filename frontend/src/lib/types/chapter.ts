/**
 * 章节相关类型定义
 */

// 单个 segment（词/句）
export interface Segment {
  text: string;
  start: number;           // 章节内时间（秒）
  end: number;
  globalId?: number;       // 全局唯一 ID（在加载时计算）
  globalStart?: number;    // 全书时间（秒）
  globalEnd?: number;
  chapterIndex?: number;   // 所属章节索引
}

// 章节元数据（manifest.json 中的格式）
export interface ChapterMeta {
  id: string;        // "ch001"
  duration: number;  // 秒
}

// 完整章节数据（加载后）
export interface Chapter extends ChapterMeta {
  index: number;           // 0, 1, 2...
  textContent?: string;    // 懒加载的文本
  segments?: Segment[];    // 懒加载的对齐数据
  audioSrc: string;        // 音频 URL
  globalStartTime: number; // 在全书中的起始时间（秒）
}

// 书籍 manifest
export interface BookManifest {
  chapters: ChapterMeta[];
  totalDuration: number;
}

// 章节加载状态
export interface ChapterLoadState {
  textLoaded: boolean;     // 文字已加载
  dataLoaded: boolean;     // 音频+对齐已加载
  isVisible: boolean;      // 是否在可视区域
  state: 'idle' | 'loading' | 'loaded' | 'error';
}
