<!--
  书籍上传页面
-->
<script lang="ts">
  import { goto } from "$app/navigation";
  import { authStore } from "$lib/stores/auth.svelte";
  import { uploadBook } from "$lib/utils/api";

  let title = $state("");
  let author = $state("");
  let description = $state("");
  let bookZip: File | null = $state(null);
  let coverFile: File | null = $state(null);

  let error = $state("");
  let isLoading = $state(false);
  let uploadProgress = $state(0);

  // 文件选择
  function handleZipSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      bookZip = input.files[0];
    }
  }

  function handleCoverSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      coverFile = input.files[0];
    }
  }

  // 上传
  async function handleSubmit(e: Event) {
    e.preventDefault();

    if (!title.trim()) {
      error = "请输入书名";
      return;
    }

    if (!bookZip) {
      error = "请选择书籍 ZIP 文件";
      return;
    }

    error = "";
    isLoading = true;

    try {
      const formData = new FormData();
      formData.append("title", title);
      if (author) formData.append("author", author);
      if (description) formData.append("description", description);
      formData.append("book_zip", bookZip);
      if (coverFile) formData.append("cover_file", coverFile);

      await uploadBook(formData);

      // 上传成功，跳转到首页
      goto("/");
    } catch (err) {
      error = err instanceof Error ? err.message : "上传失败";
    } finally {
      isLoading = false;
    }
  }

  // 格式化文件大小
  function formatSize(bytes: number): string {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }
</script>

<svelte:head>
  <title>上传书籍 - AudioBook</title>
</svelte:head>

<div
  class="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-8 px-4"
>
  <div class="max-w-2xl mx-auto">
    <!-- 头部 -->
    <div class="flex items-center gap-4 mb-8">
      <a href="/" class="p-2 hover:bg-white/50 rounded-xl transition-colors">
        <svg
          class="w-6 h-6 text-gray-600"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M15 19l-7-7 7-7"
          />
        </svg>
      </a>
      <h1 class="text-2xl font-bold text-gray-900">上传书籍</h1>
    </div>

    <!-- 上传表单 -->
    <div class="bg-white rounded-2xl shadow-xl p-8">
      <form onsubmit={handleSubmit} class="space-y-6">
        <!-- 书名 -->
        <div>
          <label
            for="title"
            class="block text-sm font-medium text-gray-700 mb-1"
          >
            书名 <span class="text-red-500">*</span>
          </label>
          <input
            id="title"
            type="text"
            bind:value={title}
            required
            class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            placeholder="输入书籍名称"
          />
        </div>

        <!-- 作者 -->
        <div>
          <label
            for="author"
            class="block text-sm font-medium text-gray-700 mb-1"
          >
            作者
          </label>
          <input
            id="author"
            type="text"
            bind:value={author}
            class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            placeholder="作者名称（可选）"
          />
        </div>

        <!-- 简介 -->
        <div>
          <label
            for="description"
            class="block text-sm font-medium text-gray-700 mb-1"
          >
            简介
          </label>
          <textarea
            id="description"
            bind:value={description}
            rows="3"
            class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all resize-none"
            placeholder="书籍简介（可选）"
          ></textarea>
        </div>

        <!-- ZIP 文件 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            书籍文件 (ZIP) <span class="text-red-500">*</span>
          </label>
          <div
            class="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center hover:border-blue-400 transition-colors"
          >
            <input
              type="file"
              accept=".zip"
              onchange={handleZipSelect}
              class="hidden"
              id="zipInput"
            />
            {#if bookZip}
              <div class="flex items-center justify-center gap-3">
                <svg
                  class="w-8 h-8 text-green-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <div class="text-left">
                  <p class="font-medium text-gray-900">{bookZip.name}</p>
                  <p class="text-sm text-gray-500">
                    {formatSize(bookZip.size)}
                  </p>
                </div>
                <button
                  type="button"
                  onclick={() => (bookZip = null)}
                  class="ml-4 p-1 text-gray-400 hover:text-red-500"
                >
                  <svg
                    class="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>
            {:else}
              <label for="zipInput" class="cursor-pointer">
                <svg
                  class="w-12 h-12 text-gray-400 mx-auto mb-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
                <p class="text-gray-600">点击选择 ZIP 文件</p>
                <p class="text-sm text-gray-400 mt-1">
                  包含 0000001.mp3/txt/json 等章节文件
                </p>
              </label>
            {/if}
          </div>
        </div>

        <!-- 封面图片 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            封面图片（可选）
          </label>
          <div
            class="border-2 border-dashed border-gray-200 rounded-xl p-4 text-center hover:border-blue-400 transition-colors"
          >
            <input
              type="file"
              accept="image/*"
              onchange={handleCoverSelect}
              class="hidden"
              id="coverInput"
            />
            {#if coverFile}
              <div class="flex items-center justify-center gap-3">
                <svg
                  class="w-6 h-6 text-green-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                  />
                </svg>
                <span class="text-gray-900">{coverFile.name}</span>
                <button
                  type="button"
                  onclick={() => (coverFile = null)}
                  class="p-1 text-gray-400 hover:text-red-500"
                >
                  <svg
                    class="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>
            {:else}
              <label
                for="coverInput"
                class="cursor-pointer text-gray-500 text-sm"
              >
                点击选择封面图片
              </label>
            {/if}
          </div>
        </div>

        <!-- 错误提示 -->
        {#if error}
          <div
            class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600"
          >
            {error}
          </div>
        {/if}

        <!-- 提交按钮 -->
        <button
          type="submit"
          disabled={isLoading}
          class="w-full py-4 px-6 bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-semibold rounded-xl hover:from-blue-600 hover:to-indigo-700 focus:ring-4 focus:ring-blue-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {#if isLoading}
            <span class="flex items-center justify-center gap-2">
              <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle
                  class="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  stroke-width="4"
                ></circle>
                <path
                  class="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                ></path>
              </svg>
              上传中...
            </span>
          {:else}
            上传书籍
          {/if}
        </button>
      </form>

      <!-- 帮助信息 -->
      <div class="mt-8 p-4 bg-blue-50 rounded-xl">
        <h3 class="font-medium text-blue-900 mb-2">ZIP 文件格式说明</h3>
        <ul class="text-sm text-blue-700 space-y-1">
          <li>
            • 每个章节需要三个文件：0000001.mp3, 0000001.txt, 0000001.json
          </li>
          <li>• 文件编号从 0000001 开始，按顺序递增</li>
          <li>• .mp3 是音频文件，.txt 是文本内容，.json 是对齐数据</li>
          <li>• 所有文件直接放在 ZIP 根目录或同一文件夹内</li>
        </ul>
      </div>
    </div>
  </div>
</div>
