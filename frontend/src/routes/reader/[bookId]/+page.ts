/**
 * 阅读器页面数据加载
 * 
 * 加载 manifest.json 和第一章内容
 */

export const ssr = false; // Disable SSR to access authStore

import type { BookManifest } from '$lib/types/chapter';
import { authStore } from '$lib/stores/auth.svelte';

interface LoadParams {
  params: { bookId: string };
  fetch: typeof globalThis.fetch;
}

export const load = async ({ params, fetch }: LoadParams) => {
  const { bookId } = params;
  
  // 开发模式：使用本地示例数据
  const isDev = import.meta.env.DEV;
  const basePath = isDev ? '/sample' : `/api/books/${bookId}`;
  
  const headers = authStore.getAuthHeader();

  try {
    // 1. 加载 manifest（章节目录）
    const manifestUrl = `${basePath}/manifest`; // API endpoint, not static file
    const manifestRes = await fetch(manifestUrl, { headers });
    if (!manifestRes.ok) {
      throw new Error(`Failed to load manifest from ${manifestUrl}`);
    }
    const manifest: BookManifest = await manifestRes.json();
    
    // 获取书籍标题
    let bookTitle = '未命名书籍';
    if (!isDev) {
      try {
        const bookInfoRes = await fetch(`/api/books/${bookId}`, { headers });
        if (bookInfoRes.ok) {
          const bookInfo = await bookInfoRes.json();
          bookTitle = bookInfo.title || bookId;
        }
      } catch {
        bookTitle = bookId;
      }
    } else {
      bookTitle = '网络国家';
    }
    
    // 2. 加载第一章的内容
    const firstChapterId = manifest.chapters[0]?.id || 'ch001';
    
    // Construct API URLs
    const textUrl = `${basePath}/chapters/${firstChapterId}/text`;
    const alignUrl = `${basePath}/chapters/${firstChapterId}/alignment`;
    
    const [textRes, alignRes] = await Promise.all([
      fetch(textUrl, { headers }),
      fetch(alignUrl, { headers }),
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
      bookTitle,
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
