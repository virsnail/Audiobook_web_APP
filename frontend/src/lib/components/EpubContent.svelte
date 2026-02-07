<script lang="ts">
  /**
   * EPUB Content Component (Scheme 2 - HTML Mode)
   *
   * Renders the current chapter's HTML content via an iframe.
   * This preserves original formatting, images, and math.
   */

  import { onMount } from "svelte";
  import { epubChaptersStore } from "$lib/stores/epub-chapters.svelte";
  import { authStore } from "$lib/stores/auth.svelte.ts";

  interface Props {
    bookId: string;
    currentChapterIndex: number;
    currentGlobalTime: number;
    isPlaying: boolean;
    onTextSeek: (globalTime: number, chapterIndex: number) => void;
  }

  let {
    bookId,
    currentChapterIndex = 0,
    currentGlobalTime = 0,
    isPlaying = false,
    onTextSeek = () => {},
  }: Props = $props();

  // Current chapter data
  let currentChapter = $derived(
    epubChaptersStore.chapters[currentChapterIndex],
  );

  // Construct iframe source URL
  let iframeSrc = $derived.by(() => {
    if (
      !bookId ||
      !currentChapter ||
      !currentChapter.filePath ||
      !authStore.token
    )
      return "";
    // Encode file path to handle spaces/special chars safely
    const encodedPath = currentChapter.filePath
      .split("/")
      .map(encodeURIComponent)
      .join("/");
    return `/api/books/${bookId}/epub_content/${encodedPath}?token=${authStore.token}`;
  });

  onMount(() => {
    console.log("✅ [EpubContent] Iframe Component mounted");
  });

  // Sync token to cookie for iframe resources (images/css)
  $effect(() => {
    if (authStore.token) {
      document.cookie = `access_token=${authStore.token}; path=/; max-age=3600; SameSite=Lax`;
    }
  });

  // Handle iframe load
  function handleIframeLoad(event: Event) {
    console.log("🖼️ [EpubContent] Iframe loaded:", iframeSrc);
    // Future: Inject scripts for highlighting or click-to-seek here
  }
</script>

<div class="epub-content-container w-full h-full flex flex-col">
  {#if currentChapter}
    <div
      class="chapter-header px-4 py-2 border-b bg-gray-50 dark:bg-gray-800 flex justify-between items-center"
    >
      <h2
        class="text-sm font-semibold truncate text-gray-700 dark:text-gray-300"
      >
        {currentChapter.title}
      </h2>
      <span class="text-xs text-gray-500">
        {currentChapterIndex + 1} / {epubChaptersStore.chapters.length}
      </span>
    </div>

    <div class="iframe-wrapper flex-1 relative bg-white">
      {#if iframeSrc}
        <iframe
          src={iframeSrc}
          class="w-full h-full border-0"
          title={currentChapter.title}
          onload={handleIframeLoad}
          sandbox="allow-same-origin allow-scripts allow-popups"
        ></iframe>
      {:else}
        <div class="flex items-center justify-center h-full text-gray-400">
          Preparing content...
        </div>
      {/if}
    </div>
  {:else}
    <div class="flex items-center justify-center h-64 text-gray-500">
      Loading chapter data...
    </div>
  {/if}
</div>

<style>
  .epub-content-container {
    height: calc(100vh - 140px); /* Adjust based on header/footer height */
  }
</style>
