/**
 * 阅读器页面数据加载
 * 
 * 加载 manifest.json 和第一章内容
 */

import type { BookManifest } from '$lib/types/chapter';

interface LoadParams {
  params: { bookId: string };
  fetch: typeof globalThis.fetch;
}

export const load = async ({ params, fetch }: LoadParams) => {
  const { bookId } = params;
  
  // 开发模式：使用本地示例数据
  const isDev = import.meta.env.DEV;
  const basePath = isDev ? '/sample' : `/api/books/${bookId}`;
  
  try {
    // 1. 加载 manifest（章节目录）
    const manifestRes = await fetch(`${basePath}/manifest.json`);
    if (!manifestRes.ok) {
      throw new Error('Failed to load manifest');
    }
    const manifest: BookManifest = await manifestRes.json();
    
    // 2. 加载第一章的内容
    const firstChapterId = manifest.chapters[0]?.id || 'ch001';
    const [textRes, alignRes] = await Promise.all([
      fetch(`${basePath}/${firstChapterId}_text.txt`),
      fetch(`${basePath}/${firstChapterId}_align.json`),
    ]);
    
    const firstChapterText = textRes.ok ? await textRes.text() : '';
    const firstChapterSegments = alignRes.ok ? await alignRes.json() : [];
    
    return {
      bookId,
      manifest,
      basePath,
      // 第一章预加载数据
      firstChapter: {
        id: firstChapterId,
        textContent: firstChapterText,
        segments: firstChapterSegments,
      },
      bookTitle: isDev ? '网络国家' : bookId,
    };
  } catch (error) {
    console.error('加载书籍数据失败:', error);
    return {
      bookId,
      manifest: { chapters: [], totalDuration: 0 },
      basePath,
      firstChapter: {
        id: 'ch001',
        textContent: '加载失败\n\n请检查文件是否存在。',
        segments: [],
      },
      bookTitle: '加载失败',
    };
  }
};
