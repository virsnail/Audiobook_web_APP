/**
 * 对齐数据类型定义
 * 基于 segments 级别的对齐（非 words 级别）
 */

/** 单个段落/句子 */
export interface Segment {
  id: number;
  start: number;  // 开始时间（秒）
  end: number;    // 结束时间（秒）
  text: string;   // 文本内容
}

/** 完整对齐数据 */
export interface AlignmentData {
  segments: Segment[];
  language: string;
  duration: number;  // 总时长（秒）
}

/** 书籍信息 */
export interface Book {
  id: string;
  title: string;
  author?: string;
  cover_path?: string;
  storage_path: string;
  total_duration: number;
  total_segments: number;
  is_public: boolean;
  created_at: string;
}

/** 阅读进度 */
export interface ReadingProgress {
  book_id: string;
  current_position: number;  // 当前播放位置（秒）
  current_segment: number;   // 当前段落索引
  playback_speed: number;    // 播放速度
}
