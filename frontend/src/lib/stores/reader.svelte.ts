/**
 * 阅读器状态管理
 * 使用 Svelte 5 的 runes ($state, $derived)
 */

import type { Segment, AlignmentData } from '$lib/types/alignment';

/** 可用的播放速度 */
export const PLAYBACK_SPEEDS = [3, 2.5, 2.25, 2, 1.75, 1.5, 1.25, 1.0, 0.7];

/** 阅读器状态 */
function createReaderStore() {
  // 基础状态
  let currentTime = $state(0);
  let duration = $state(0);
  let isPlaying = $state(false);
  let playbackSpeed = $state(1.0);
  let segments = $state<Segment[]>([]);
  let isLoading = $state(true);
  let error = $state<string | null>(null);
  let isUserScrolling = $state(false);
  
  // 派生状态：当前高亮的段落索引
  const currentSegmentIndex = $derived.by(() => {
    if (segments.length === 0) return -1;
    
    const time = currentTime;
    let left = 0;
    let right = segments.length - 1;
    
    while (left <= right) {
      const mid = Math.floor((left + right) / 2);
      const segment = segments[mid];
      
      if (time >= segment.start && time < segment.end) {
        return mid;
      } else if (time < segment.start) {
        right = mid - 1;
      } else {
        left = mid + 1;
      }
    }
    
    return Math.max(0, left - 1);
  });
  
  // 派生状态：当前段落
  const currentSegment = $derived.by(() => {
    const index = currentSegmentIndex;
    if (index >= 0 && index < segments.length) {
      return segments[index];
    }
    return null;
  });
  
  // 派生状态：进度百分比
  const progress = $derived(duration === 0 ? 0 : (currentTime / duration) * 100);
  
  // 格式化时间
  function formatTime(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    
    if (h > 0) {
      return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
  }
  
  const formattedCurrentTime = $derived(formatTime(currentTime));
  const formattedDuration = $derived(formatTime(duration));
  
  return {
    // 状态 getters
    get currentTime() { return currentTime; },
    get duration() { return duration; },
    get isPlaying() { return isPlaying; },
    get playbackSpeed() { return playbackSpeed; },
    get segments() { return segments; },
    get isLoading() { return isLoading; },
    get error() { return error; },
    get isUserScrolling() { return isUserScrolling; },
    get currentSegmentIndex() { return currentSegmentIndex; },
    get currentSegment() { return currentSegment; },
    get progress() { return progress; },
    get formattedCurrentTime() { return formattedCurrentTime; },
    get formattedDuration() { return formattedDuration; },
    
    // 状态 setters
    set duration(value: number) { duration = value; },
    
    // 方法
    loadAlignment(data: AlignmentData) {
      segments = data.segments;
      duration = data.duration;
      isLoading = false;
      error = null;
    },
    
    updateTime(time: number) {
      currentTime = time;
    },
    
    setPlaying(playing: boolean) {
      isPlaying = playing;
    },
    
    togglePlay() {
      isPlaying = !isPlaying;
    },
    
    setSpeed(speed: number) {
      playbackSpeed = speed;
    },
    
    seekTo(time: number) {
      currentTime = Math.max(0, Math.min(time, duration));
    },
    
    seekToSegment(segmentIndex: number) {
      if (segmentIndex >= 0 && segmentIndex < segments.length) {
        currentTime = segments[segmentIndex].start;
      }
    },
    
    forward(seconds: number = 15) {
      currentTime = Math.min(currentTime + seconds, duration);
    },
    
    backward(seconds: number = 15) {
      currentTime = Math.max(currentTime - seconds, 0);
    },
    
    nextSpeed() {
      const currentIndex = PLAYBACK_SPEEDS.indexOf(playbackSpeed);
      const nextIndex = (currentIndex + 1) % PLAYBACK_SPEEDS.length;
      playbackSpeed = PLAYBACK_SPEEDS[nextIndex];
    },
    
    setUserScrolling(scrolling: boolean) {
      isUserScrolling = scrolling;
    },
    
    setError(err: string) {
      error = err;
      isLoading = false;
    },
    
    reset() {
      currentTime = 0;
      duration = 0;
      isPlaying = false;
      segments = [];
      isLoading = true;
      error = null;
    },
  };
}

/** 全局阅读器状态实例 */
export const readerStore = createReaderStore();

