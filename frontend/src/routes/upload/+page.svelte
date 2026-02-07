<!--
  书籍上传页面
-->
<script lang="ts">
  import { goto } from "$app/navigation";
  import { authStore } from "$lib/stores/auth.svelte.ts";
  import { uploadBook, uploadTxtBook, logActivity } from "$lib/utils/api";

  // 上传模式: 'zip' | 'txt'
  let uploadMode: "zip" | "txt" = $state("txt"); // 默认 TXT/MD 模式
  let selectedVoice = $state("zh-CN-YunyangNeural"); // 默认中文语音

  let title = $state("");
  let author = $state("");
  let description = $state("");

  // ZIP 模式
  let bookZip: File | null = $state(null);
  let coverFile: File | null = $state(null);

  // TXT/MD 模式
  let txtFile: File | null = $state(null);
  let textContent = $state("");

  let error = $state("");
  let isLoading = $state(false);
  let uploadProgress = $state(0);

  // ZIP 文件选择
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

  // TXT 文件选择
  function handleTxtSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      txtFile = input.files[0];
      textContent = ""; // 清空粘贴内容
    }
  }

  // 上传
  async function handleSubmit(e: Event) {
    e.preventDefault();
    logActivity("START_UPLOAD", { mode: uploadMode });

    if (!title.trim()) {
      error = "请输入书名";
      return;
    }

    if (uploadMode === "zip") {
      // ZIP 模式
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
        goto("/");
      } catch (err) {
        error = err instanceof Error ? err.message : "上传失败";
      } finally {
        isLoading = false;
      }
    } else {
      // TXT/MD 模式
      if (!txtFile && !textContent.trim()) {
        error =
          "请上传 TXT/MD 文件或粘贴文本内容. Upload TXT/MD file or paste text content.";
        return;
      }

      error = "";
      isLoading = true;

      try {
        const formData = new FormData();
        formData.append("title", title);
        if (author) formData.append("author", author);
        if (description) formData.append("description", description);
        formData.append("voice", selectedVoice); // 添加语音参数
        if (coverFile) formData.append("cover_file", coverFile); // [NEW] 添加封面

        if (txtFile) {
          formData.append("txt_file", txtFile);
        } else {
          formData.append("text_content", textContent);
        }

        await uploadTxtBook(formData);
        goto("/");
      } catch (err) {
        error = err instanceof Error ? err.message : "上传失败/Upload failed";
      } finally {
        isLoading = false;
      }
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
  <title>上传书籍 Upload Book - AudioBook</title>
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
      <h1 class="text-2xl font-bold text-gray-900">上传书籍 Upload Book</h1>
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
            书名 Title <span class="text-red-500">*</span>
          </label>
          <input
            id="title"
            type="text"
            bind:value={title}
            required
            class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            placeholder="输入书籍名称 Enter book title"
          />
        </div>

        <!-- 作者 -->
        <div>
          <label
            for="author"
            class="block text-sm font-medium text-gray-700 mb-1"
          >
            作者 Author
          </label>
          <input
            id="author"
            type="text"
            bind:value={author}
            class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            placeholder="作者名称（可选）Author Name (Optional)"
          />
        </div>

        <!-- 简介 -->
        <div>
          <label
            for="description"
            class="block text-sm font-medium text-gray-700 mb-1"
          >
            简介 Description
          </label>
          <textarea
            id="description"
            bind:value={description}
            rows="3"
            class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all resize-none"
            placeholder="书籍简介（可选）Description (Optional)"
          ></textarea>
        </div>

        <!-- 上传模式切换 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            上传方式 Upload Mode <span class="text-red-500">*</span>
          </label>
          <div class="flex gap-2">
            <button
              type="button"
              onclick={() => (uploadMode = "txt")}
              class="flex-1 py-3 px-4 rounded-xl font-medium transition-all {uploadMode ===
              'txt'
                ? 'bg-green-500 text-white shadow-lg'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}"
            >
              📚 TXT/MD 文本
            </button>
            <button
              type="button"
              onclick={() => (uploadMode = "zip")}
              class="flex-1 py-3 px-4 rounded-xl font-medium transition-all {uploadMode ===
              'zip'
                ? 'bg-blue-500 text-white shadow-lg'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}"
            >
              📦 ZIP 压缩包
            </button>
          </div>
          <p class="text-xs text-gray-400 mt-2">
            {uploadMode === "zip"
              ? "上传已准备好的有声书文件包"
              : "支持 TXT/MD 格式，服务器自动生成有声书（等待处理完毕，才能成功打开书籍）Supports TXT/MD. Server auto-generates audiobooks (need to wait for processing to open books)"}
          </p>
        </div>

        {#if uploadMode === "zip"}
          <!-- ZIP 文件 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              书籍文件 (ZIP) Book File <span class="text-red-500">*</span>
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
                  <p class="text-gray-600">
                    点击选择 ZIP 文件 Click to select ZIP
                  </p>
                  <p class="text-sm text-gray-400 mt-1">
                    必须包含 0000001.mp3/txt/json
                    章节文件+音频文件+对齐文件。也可以包含书籍封面图片。 Must
                    contains chapter files + mp3 files + json files. And can
                    also include book cover image.
                  </p>
                </label>
              {/if}
            </div>
          </div>
        {:else}
          <!-- TXT/MD 模式 -->
          <div class="space-y-4">
            <!-- TXT 文件上传 -->
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">
                上传 TXT/MD 文件 Upload TXT/MD File
              </label>
              <div
                class="border-2 border-dashed border-gray-200 rounded-xl p-4 text-center hover:border-green-400 transition-colors"
              >
                <input
                  type="file"
                  accept=".txt,.md"
                  onchange={handleTxtSelect}
                  class="hidden"
                  id="txtInput"
                />
                {#if txtFile}
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
                        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    <span class="text-gray-900">{txtFile.name}</span>
                    <span class="text-sm text-gray-500"
                      >{formatSize(txtFile.size)}</span
                    >
                    <button
                      type="button"
                      onclick={() => (txtFile = null)}
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
                    for="txtInput"
                    class="cursor-pointer text-gray-500 text-sm"
                  >
                    点击上传 TXT/MD 文件 Click to upload TXT/MD
                  </label>
                {/if}
              </div>
            </div>

            <!-- 或者分隔线 -->
            <div class="flex items-center gap-4">
              <div class="flex-1 h-px bg-gray-200"></div>
              <span class="text-sm text-gray-400">或 OR</span>
              <div class="flex-1 h-px bg-gray-200"></div>
            </div>

            <!-- 文本粘贴 -->
            <div>
              <label
                for="textContent"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                直接粘贴文本 Paste Text Directly
              </label>
              <textarea
                id="textContent"
                bind:value={textContent}
                rows="10"
                disabled={!!txtFile}
                class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-transparent transition-all resize-none disabled:bg-gray-100 disabled:cursor-not-allowed"
                placeholder="在此粘贴文章内容...&#10;Paste your article content here..."
              ></textarea>
              <p class="text-xs text-gray-400 mt-1">
                ⚠️ 服务器将自动生成音频，处理时间取决于文本长度
              </p>
            </div>
          </div>
        {/if}

        <!-- 封面图片 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            封面图片（可选）Cover Image (Optional)
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
                点击选择封面图片 Click to select cover
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

        <!-- 朗读声音选择 (仅 TXT 模式) -->
        {#if uploadMode === "txt"}
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              朗读声音 Voice Selection
            </label>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label
                class="relative flex items-center p-4 border rounded-xl cursor-pointer hover:bg-gray-50 transition-colors {selectedVoice ===
                'zh-CN-YunyangNeural'
                  ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500'
                  : 'border-gray-200'}"
              >
                <input
                  type="radio"
                  name="voice"
                  value="zh-CN-YunyangNeural"
                  bind:group={selectedVoice}
                  class="h-4 w-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                />
                <div class="ml-3">
                  <span class="block text-sm font-medium text-gray-900">
                    中文 - 云扬 (默认)
                  </span>
                  <span class="block text-xs text-gray-500"
                    >zh-CN-YunyangNeural</span
                  >
                </div>
              </label>

              <label
                class="relative flex items-center p-4 border rounded-xl cursor-pointer hover:bg-gray-50 transition-colors {selectedVoice ===
                'en-US-BrianNeural'
                  ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500'
                  : 'border-gray-200'}"
              >
                <input
                  type="radio"
                  name="voice"
                  value="en-US-BrianNeural"
                  bind:group={selectedVoice}
                  class="h-4 w-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                />
                <div class="ml-3">
                  <span class="block text-sm font-medium text-gray-900">
                    English - Brian
                  </span>
                  <span class="block text-xs text-gray-500"
                    >en-US-BrianNeural</span
                  >
                </div>
              </label>
            </div>
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
              上传中... Uploading...
            </span>
          {:else}
            上传书籍 Upload Book
          {/if}
        </button>
      </form>

      <!-- 帮助信息 -->
      <div class="mt-8 p-4 bg-blue-50 rounded-xl">
        <h3 class="font-medium text-blue-900 mb-2">
          ZIP 文件格式说明 ZIP Format Guide
        </h3>
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
