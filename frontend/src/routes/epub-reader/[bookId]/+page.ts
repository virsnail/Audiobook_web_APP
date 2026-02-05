/**
 * EPUB Reader Page Load Function (方案2)
 * 服务器端加载 EPUB manifest 和书籍信息
 */

export const ssr = false; // Disable SSR to access authStore

import { error } from "@sveltejs/kit";
import type { PageLoad } from "./$types";
import { authStore } from '$lib/stores/auth.svelte';

export const load: PageLoad = async ({ params, fetch }) => {
  const bookId = params.bookId;

  console.log("🔍 [EPUB Page Load] Loading book:", bookId);

  // 获取认证 header
  const headers = authStore.getAuthHeader();

  try {
    // 1. 获取书籍基本信息
    const bookResponse = await fetch(`/api/books/${bookId}`, { headers });

    if (!bookResponse.ok) {
      console.error("❌ [EPUB Page Load] Failed to load book:", bookResponse.status);
      throw error(bookResponse.status, "无法加载书籍信息");
    }

    const book = await bookResponse.json();
    console.log("✅ [EPUB Page Load] Book loaded:", book);

    // 2. 验证是否为 EPUB 格式
    if (book.book_type !== "epub") {
      console.error("❌ [EPUB Page Load] Book is not EPUB type:", book.book_type);
      throw error(400, "此书籍不是 EPUB 格式");
    }

    //3. 获取 EPUB manifest
    const manifestResponse = await fetch(`/api/books/${bookId}/epub/manifest`, { headers });

    if (!manifestResponse.ok) {
      console.error("❌ [EPUB Page Load] Failed to load EPUB manifest:", manifestResponse.status);
      throw error(manifestResponse.status, "无法加载 EPUB 结构");
    }

    const epubManifest = await manifestResponse.json();
    console.log("✅ [EPUB Page Load] EPUB manifest loaded:", {
      chapters: epubManifest.chapters?.length || 0,
      metadata: epubManifest.metadata,
    });

    return {
      bookId,
      book,
      epubManifest,
    };
  } catch (err) {
    console.error("❌ [EPUB Page Load] Error:", err);
    throw err;
  }
};
