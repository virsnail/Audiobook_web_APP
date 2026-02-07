/**
 * EPUB Chapters Store (方案2专用)
 * 
 * 完全独立于 chapters.svelte (方案1)
 * 管理EPUB章节的HTML内容和对齐数据
 */

import type { Segment } from "$lib/types/chapter";

interface EpubChapter {
  id: string; // 例如 "001"
  order: number;
  title: string;
  href: string; // EPUB HTML文件路径
  filePath: string; // 相对于 epub 根目录的路径 (用于 iframe src)
  epubId: string; // OPF中的ID
  audioFile: string; // 例如 "ch001_audio.mp3"
  alignmentFile: string; // 例如 "ch001_align.json"
  audioSrc: string; // HTTP URL
  htmlContent?: string; // HTML内容
  segments?: Segment[];
  duration: number;
  globalStartTime: number;
  isVisible: boolean;
  isLoaded: boolean;
}

class EpubChaptersStore {
  chapters = $state<EpubChapter[]>([]);
  totalDuration = $state(0);
  bookId = $state("");

  initFromManifest(manifest: any, bookId: string) {
    this.bookId = bookId;
    this.chapters = [];
    let globalTime = 0;

    for (const ch of manifest.chapters || []) {
      const chapter: EpubChapter = {
        id: ch.id,
        order: ch.order,
        title: ch.title || `Chapter ${ch.id}`,
        href: ch.href,
        filePath: ch.file_path || ch.href, // Fallback if missing
        epubId: ch.epub_id,
        audioFile: ch.audio_file,
        alignmentFile: ch.alignment_file,
        audioSrc: `/api/books/${bookId}/chapters/${ch.id}/audio`,
        duration: 0, // Will be calculated from alignment
        globalStartTime: globalTime,
        isVisible: false,
        isLoaded: false,
      };

      this.chapters.push(chapter);
    }
  }

  async loadAllBookData() {
    console.log("📥 Loading all EPUB book data...");

    for (let i = 0; i < this.chapters.length; i++) {
      await this.loadChapterData(i);
    }

    console.log("✅ All EPUB data loaded");
  }

  async loadChapterData(index: number) {
    const chapter = this.chapters[index];
    if (!chapter || chapter.isLoaded) return;

    console.log(`📥 Loading EPUB chapter ${index}: ${chapter.id}`);

    try {
      // 1. 加载HTML内容 (暂时跳过,直接从EPUB读取会更复杂,后面实现)
      // chapter.htmlContent = await loadEpubChapterHtml(this.bookId, chapter.href);

      // 2. 加载对齐数据 - 使用相对路径通过 nginx 代理
      // 需要添加认证头
      const { authStore } = await import("$lib/stores/auth.svelte.ts");
      const headers = authStore.getAuthHeader();
      
      const response = await fetch(
        `/api/books/${this.bookId}/chapters/${chapter.id}/alignment`,
        { headers }
      );

      if (!response.ok) {
        throw new Error(`Failed to load alignment for chapter ${chapter.id}`);
      }

      const alignData = await response.json();
      const segments: Segment[] = Array.isArray(alignData)
        ? alignData
        : alignData.segments || [];

      // 添加全局信息
      let globalId = 0;
      for (const seg of segments) {
        seg.globalId = globalId++;
        seg.globalStart = chapter.globalStartTime + seg.start;
        seg.globalEnd = chapter.globalStartTime + seg.end;
        seg.chapterIndex = index;
      }

      chapter.segments = segments;

      // 计算章节时长
      if (segments.length > 0) {
        chapter.duration = segments[segments.length - 1].end;
      }

      chapter.isLoaded = true;

      // 更新总时长和后续章节的全局开始时间
      this.recalculateGlobalTimes();
    } catch (err) {
      console.error(`Failed to load EPUB chapter ${chapter.id}:`, err);
    }
  }

  recalculateGlobalTimes() {
    let globalTime = 0;
    for (const ch of this.chapters) {
      ch.globalStartTime = globalTime;
      globalTime += ch.duration;
    }
    this.totalDuration = globalTime;
  }

  setChapterVisibility(index: number, visible: boolean) {
    if (this.chapters[index]) {
      this.chapters[index].isVisible = visible;
    }
  }

  globalToChapterTime(globalTime: number): {
    chapterIndex: number;
    chapterTime: number;
  } {
    for (let i = 0; i < this.chapters.length; i++) {
      const ch = this.chapters[i];
      const nextStart =
        i < this.chapters.length - 1
          ? this.chapters[i + 1].globalStartTime
          : Infinity;

      if (globalTime >= ch.globalStartTime && globalTime < nextStart) {
        return {
          chapterIndex: i,
          chapterTime: globalTime - ch.globalStartTime,
        };
      }
    }

    return { chapterIndex: 0, chapterTime: 0 };
  }

  getChapterIndexByGlobalTime(globalTime: number): number {
    return this.globalToChapterTime(globalTime).chapterIndex;
  }
}

export const epubChaptersStore = new EpubChaptersStore();
