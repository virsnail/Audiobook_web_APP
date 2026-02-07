/**
 * 阅读器页面数据加载
 * 
 * 加载 manifest.json 和第一章内容
 */

export const ssr = false; // Disable SSR to access authStore

import type { BookManifest } from '$lib/types/chapter';
import { authStore } from '$lib/stores/auth.svelte.ts';

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
    // 1. 先获取书籍信息，检查处理状态
    let bookTitle = '未命名书籍';
    let processingStatus = 'ready';
    let processingError = '';
    
    if (!isDev) {
      try {
        const bookInfoRes = await fetch(`/api/books/${bookId}`, { headers });
        if (bookInfoRes.ok) {
          const bookInfo = await bookInfoRes.json();
          bookTitle = bookInfo.title || bookId;
          processingStatus = bookInfo.processing_status || 'ready';
          processingError = bookInfo.processing_error || '';
        } else if (bookInfoRes.status === 404) {
           throw new Error("书籍不存在 / Book not found");
        }
      } catch (e) {
        console.error("Failed to fetch book info:", e);
        // 如果获取书籍信息失败，假设是现成的（可能是旧数据或网络问题），尝试继续加载 manifest
        processingStatus = 'ready'; 
      }
    } else {
       bookTitle = 'Demo Book';
    }

    // 如果书籍还在处理中或失败，直接返回状态，不加载 manifest
    if (processingStatus === 'processing' || processingStatus === 'pending' || processingStatus === 'failed') {
      return {
        bookId,
        manifest: { chapters: [], totalDuration: 0 },
        basePath,
        firstChapter: {
          id: 'ch001',
          textContent: '',
          segments: [],
        },
        bookTitle,
        processingStatus,
        processingError,
      };
    }

    // 2. 加载 manifest（章节目录）
    // 只有当状态是 ready/completed 时才尝试加载
    const manifestUrl = `${basePath}/manifest`;
    const manifestRes = await fetch(manifestUrl, { headers });
    if (!manifestRes.ok) {
      // 如果 manifest 不存在，但状态显示 ready，可能是个错误
      if (manifestRes.status === 404) {
          // Double check status or consider it a failure requiring admin attention
          console.error(`Manifest 404 for book ${bookId}`);
          return {
            bookId,
            manifest: { chapters: [], totalDuration: 0 },
            basePath,
            firstChapter: { id: '', textContent: '', segments: [] },
            bookTitle,
            processingStatus: 'missing_manifest', // 自定义状态用于前端显示
            processingError: 'Manifest file missing. Please contact admin.',
          };
      }
      throw new Error(`Failed to load manifest from ${manifestUrl}`);
    }
    const manifest: BookManifest = await manifestRes.json();
    
    // 3. 加载第一章的内容
    const firstChapterId = manifest.chapters[0]?.id || 'ch001';
    
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
      firstChapter: {
        id: firstChapterId,
        textContent: firstChapterText,
        segments: firstChapterSegments,
      },
      bookTitle,
      processingStatus: 'ready', 
      processingError: '',
    };
  } catch (error) {
    console.error('加载书籍数据失败:', error);
    return {
      bookId,
      manifest: { chapters: [], totalDuration: 0 },
      basePath,
      firstChapter: {
        id: 'ch001',
        textContent: '加载失败 / Load Failed\n\n请检查网络或刷新重试。 Please check network or retry.',
        segments: [],
      },
      bookTitle: '加载失败',
      processingStatus: 'error',
      processingError: error instanceof Error ? error.message : String(error),
    };
  }
};
