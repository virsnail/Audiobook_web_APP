<!--
  首页 - 书架
-->
<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { authStore } from "$lib/stores/auth.svelte";
  import {
    getBooks,
    deleteBook,
    shareBook,
    getBookShares,
    unshareBook,
    changePassword,
    logout,
    logActivity,
    type Book,
  } from "$lib/utils/api";

  // 书籍列表
  let books = $state<Book[]>([]);
  let isLoading = $state(true);
  let error = $state("");

  // 分享对话框
  let showShareDialog = $state(false);
  let shareBookId = $state("");
  let shareEmail = $state("");
  let shareLoading = $state(false);
  let shareError = $state("");

  // 分享状态
  let shareStatus = $state<{
    is_public: boolean;
    shared_users: Array<{
      email: string;
      nickname: string;
      shared_at: string | null;
    }>;
    total_shares: number;
  } | null>(null);
  let shareStatusLoading = $state(false);

  // 修改密码状态
  let showPasswordDialog = $state(false);
  let newPassword = $state("");
  let emailCode = $state(""); // [NEW] 邮箱验证码
  let changePasswordLoading = $state(false);
  let changePasswordError = $state("");
  let codeSent = $state(false); // [NEW] 验证码发送状态
  let codeSending = $state(false); // [NEW] 验证码发送中
  let countdown = $state(0); // [NEW] 倒计时

  // ... (保留中间代码) ...

  // 打开修改密码对话框
  function openPasswordDialog() {
    newPassword = "";
    emailCode = "";
    changePasswordError = "";
    codeSent = false;
    showPasswordDialog = true;
  }

  // 发送验证码
  async function handleSendCode() {
    if (!authStore.user?.email) return;

    codeSending = true;
    changePasswordError = "";

    try {
      await sendEmailCode(authStore.user.email);
      codeSent = true;
      startCountdown();
      alert("验证码已发送到您的邮箱\nVerification code sent to your email");
    } catch (err) {
      changePasswordError =
        err instanceof Error
          ? err.message
          : "验证码发送失败 Failed to send code";
    } finally {
      codeSending = false;
    }
  }

  // 倒计时逻辑
  function startCountdown() {
    countdown = 60;
    const timer = setInterval(() => {
      countdown--;
      if (countdown <= 0) {
        clearInterval(timer);
      }
    }, 1000);
  }

  // 处理修改密码
  async function handleChangePassword() {
    if (!emailCode) {
      changePasswordError =
        "请输入邮箱验证码 Please enter email verification code";
      return;
    }
    if (!newPassword) {
      changePasswordError = "请输入新密码 Please enter a new password";
      return;
    }
    if (newPassword.length < 6) {
      changePasswordError =
        "密码长度至少需要6位 Password must be at least 6 characters";
      return;
    }

    changePasswordLoading = true;
    changePasswordError = "";

    try {
      await changePassword(newPassword, emailCode); // [MODIFY] 传递验证码
      alert("密码修改成功！Password changed successfully!");
      showPasswordDialog = false;
    } catch (err) {
      changePasswordError =
        err instanceof Error
          ? err.message
          : "修改失败 Failed to change password";
    } finally {
      changePasswordLoading = false;
    }
  }
</script>

<svelte:head>
  <title>我的书架 Bookshelf - AudioBook</title>
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1, viewport-fit=cover"
  />
</svelte:head>

<div class="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100">
  <!-- 顶部标题栏 -->
  <header
    class="sticky top-0 bg-white/95 backdrop-blur-sm border-b border-gray-200 z-10 safe-area-top"
  >
    <div class="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900">我的书架 Bookshelf</h1>

      <div class="flex items-center gap-3">
        {#if authStore.isLoggedIn}
          <!-- 上传按钮 -->
          <a
            href="/upload"
            onclick={() => logActivity("NAVIGATE_UPLOAD")}
            class="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600 transition-colors"
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
                d="M12 4v16m8-8H4"
              />
            </svg>
            <span class="hidden sm:inline">上传 Upload</span>
          </a>

          <!-- 用户菜单 -->
          <div class="relative group">
            <button
              class="flex items-center gap-2 px-3 py-2 rounded-xl hover:bg-gray-100 transition-colors"
            >
              <div
                class="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center text-white text-sm font-medium"
              >
                {authStore.user?.nickname?.charAt(0) ||
                  authStore.user?.email?.charAt(0) ||
                  "U"}
              </div>
              <svg
                class="w-4 h-4 text-gray-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>

            <div
              class="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-lg border border-gray-100 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all"
            >
              <div class="px-4 py-3 border-b border-gray-100">
                <p class="font-medium text-gray-900">
                  {authStore.user?.nickname || "用户 User"}
                </p>
                <p class="text-sm text-gray-500 truncate">
                  {authStore.user?.email}
                </p>
              </div>
              <button
                onclick={openPasswordDialog}
                class="w-full px-4 py-3 text-left text-gray-700 hover:bg-gray-50 transition-colors border-b border-gray-100"
              >
                修改密码 Change Password
              </button>
              <button
                onclick={handleLogout}
                class="w-full px-4 py-3 text-left text-red-600 hover:bg-red-50 transition-colors rounded-b-xl"
              >
                退出登录 Logout
              </button>
            </div>
          </div>
        {:else}
          <a
            href="/login"
            class="px-4 py-2 text-blue-600 hover:bg-blue-50 rounded-xl transition-colors"
          >
            登录 Login
          </a>
          <a
            href="/register"
            class="px-4 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600 transition-colors"
          >
            注册 Register
          </a>
        {/if}
      </div>
    </div>
  </header>

  <!-- 书籍网格 -->
  <main class="max-w-6xl mx-auto px-4 py-6">
    {#if isLoading}
      <div class="flex items-center justify-center py-20">
        <svg
          class="animate-spin w-8 h-8 text-blue-500"
          fill="none"
          viewBox="0 0 24 24"
        >
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
      </div>
    {:else if error}
      <div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600">
        {error}
      </div>
    {:else if authStore.isLoggedIn}
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        <!-- 已登录用户的书籍 -->
        {#each books as book, i}
          <div
            class="group bg-white rounded-2xl shadow-sm hover:shadow-lg transition-all duration-300 overflow-hidden border border-gray-100"
          >
            <!-- 封面 -->
            <div
              onclick={(e) => handleBookClick(book, e)}
              class="block relative cursor-pointer"
            >
              <div
                class="aspect-[4/3] flex items-end p-4 bg-cover bg-center"
                style="background-image: {getBookCover(book, i)}"
              >
                <!-- 处理状态标识 -->
                {#if book.processing_status === "processing"}
                  <div
                    class="absolute top-2 left-2 px-2 py-1 bg-yellow-500 text-white text-xs rounded-full font-medium shadow-lg animate-pulse"
                  >
                    ⏳ 生成中...
                  </div>
                {:else if book.processing_status === "failed"}
                  <div
                    class="absolute top-2 left-2 px-2 py-1 bg-red-500 text-white text-xs rounded-full font-medium shadow-lg"
                  >
                    ❌ 生成失败
                  </div>
                {/if}
                <div class="w-full">
                  <h2
                    class="text-xl font-bold text-white drop-shadow-lg line-clamp-2"
                  >
                    {book.title}
                  </h2>
                  {#if book.author}
                    <p class="text-white/80 text-sm mt-1">{book.author}</p>
                  {/if}
                </div>
              </div>
            </div>

            <!-- 信息和操作 -->
            <div class="p-4">
              <p class="text-gray-500 text-sm line-clamp-2">
                {book.description || "暂无简介 No Description"}
              </p>

              <!-- 操作按钮 -->
              <div class="mt-3 flex items-center justify-between">
                <button
                  onclick={(e) => handleBookClick(book, e)}
                  class="flex items-center text-blue-600 text-sm font-medium hover:text-blue-700 transition-colors"
                >
                  <span>开始阅读 Read</span>
                  <svg
                    class="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                </button>

                <div class="flex items-center gap-2">
                  <!-- 分享按钮 -->
                  <button
                    onclick={() => openShareDialog(book.id)}
                    class="p-2 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg transition-colors"
                    title="分享 Share"
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
                        d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
                      />
                    </svg>
                  </button>

                  <!-- 删除按钮 -->
                  <button
                    onclick={() => handleDelete(book.id)}
                    class="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    title="删除 Delete"
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
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        {:else}
          <!-- 空状态 -->
          <div class="col-span-full text-center py-16">
            <svg
              class="w-16 h-16 text-gray-300 mx-auto mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
              />
            </svg>
            <h3 class="text-lg font-medium text-gray-900">
              还没有书籍 No Books
            </h3>
            <p class="text-gray-500 mt-1">
              上传你的第一本书开始阅读吧 Upload your first book
            </p>
            <a
              href="/upload"
              class="inline-flex items-center gap-2 mt-4 px-6 py-3 bg-blue-500 text-white rounded-xl hover:bg-blue-600 transition-colors"
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
                  d="M12 4v16m8-8H4"
                />
              </svg>
              上传书籍 Upload Book
            </a>
          </div>
        {/each}
      </div>
    {:else}
      <!-- 未登录显示 Landing Page -->
      <div class="py-16 text-center">
        <div class="max-w-3xl mx-auto">
          <h2
            class="text-4xl sm:text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600 mb-6"
          >
            AudioBook Reader
          </h2>
          <p class="text-xl text-gray-600 mb-10 leading-relaxed">
            沉浸式有声书阅读体验 Immersive Audiobook Experience<br />
            实时文本对齐，深度学习的最佳伴侣 Real-time Text Alignment
          </p>

          <div
            class="flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            <a
              href="/login"
              class="w-full sm:w-auto px-8 py-3.5 bg-blue-600 text-white font-medium rounded-xl hover:bg-blue-700 transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5"
            >
              立即登录 Login Now
            </a>
            <a
              href="/register"
              class="w-full sm:w-auto px-8 py-3.5 bg-white text-gray-700 font-medium rounded-xl border border-gray-200 hover:bg-gray-50 hover:border-gray-300 transition-all shadow-sm hover:shadow-md hover:-translate-y-0.5"
            >
              注册账号 Register Account
            </a>
          </div>

          <!-- 特性展示 -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mt-20 text-left">
            <div
              class="p-6 bg-white rounded-2xl shadow-sm border border-gray-100"
            >
              <div
                class="w-12 h-12 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center mb-4"
              >
                <svg
                  class="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                  />
                </svg>
              </div>
              <h3 class="font-bold text-gray-900 text-lg mb-2">文本同步</h3>
              <p class="text-gray-500 text-sm">
                精确到句子的音频文本对齐，所听即所读，提升学习效率。
              </p>
            </div>

            <div
              class="p-6 bg-white rounded-2xl shadow-sm border border-gray-100"
            >
              <div
                class="w-12 h-12 bg-purple-50 text-purple-600 rounded-xl flex items-center justify-center mb-4"
              >
                <svg
                  class="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"
                  />
                </svg>
              </div>
              <h3 class="font-bold text-gray-900 text-lg mb-2">沉浸体验</h3>
              <p class="text-gray-500 text-sm">
                极简设计，专注阅读本质。支持深色模式，保护视力。
              </p>
            </div>

            <div
              class="p-6 bg-white rounded-2xl shadow-sm border border-gray-100"
            >
              <div
                class="w-12 h-12 bg-green-50 text-green-600 rounded-xl flex items-center justify-center mb-4"
              >
                <svg
                  class="w-6 h-6"
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
              </div>
              <h3 class="font-bold text-gray-900 text-lg mb-2">私有部署</h3>
              <p class="text-gray-500 text-sm">
                完全掌握自己的数据，Docker 一键部署，安全可靠。
              </p>
            </div>
          </div>
        </div>
      </div>
    {/if}
  </main>
</div>

<!-- 分享对话框 -->
{#if showShareDialog}
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
  >
    <div class="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
      <h3 class="text-xl font-bold text-gray-900 mb-4">分享书籍 Share Book</h3>

      <!-- 当前分享状态 -->
      {#if shareStatusLoading}
        <div class="mb-4 p-4 bg-gray-50 rounded-xl">
          <p class="text-sm text-gray-500">加载中... Loading...</p>
        </div>
      {:else if shareStatus}
        <div class="mb-4 p-4 bg-blue-50 rounded-xl border border-blue-200">
          <h4 class="font-medium text-gray-800 mb-3">
            当前分享状态 Current Share Status
          </h4>

          <!-- 公开分享状态 -->
          <div class="mb-3 flex items-center">
            <span class="text-sm font-medium text-gray-700 mr-2">
              公开分享 Public Share:
            </span>
            {#if shareStatus.is_public}
              <span class="text-green-600 font-medium">✓ 已公开 Public</span>
            {:else}
              <span class="text-gray-500">✗ 未公开 Not Public</span>
            {/if}
          </div>

          <!-- 分享用户列表 -->
          {#if shareStatus.shared_users && shareStatus.shared_users.length > 0}
            <div>
              <p class="text-sm font-medium text-gray-700 mb-2">
                已分享给 Shared with ({shareStatus.total_shares}):
              </p>
              <div class="space-y-1 max-h-32 overflow-y-auto">
                {#each shareStatus.shared_users as user}
                  <div class="text-sm text-gray-600 bg-white px-2 py-1 rounded">
                    • {user.email}
                    {#if user.nickname}
                      ({user.nickname})
                    {/if}
                  </div>
                {/each}
              </div>
            </div>
          {:else if !shareStatus.is_public}
            <p class="text-sm text-gray-500">尚未分享 Not shared yet</p>
          {/if}

          <!-- 取消所有分享按钮 -->
          {#if shareStatus.is_public || shareStatus.total_shares > 0}
            <button
              onclick={handleUnshare}
              disabled={shareLoading}
              class="w-full mt-3 py-2 bg-red-500 text-white rounded-xl hover:bg-red-600 disabled:opacity-50 text-sm font-medium"
            >
              🗑️ 取消所有分享 Cancel All Shares
            </button>
          {/if}
        </div>

        <div class="mb-3 text-center text-gray-500 text-sm">
          添加新分享 Add New Share
        </div>
      {/if}

      <!-- 分享给指定用户 -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-1">
          分享给指定用户 Share to User
        </label>
        <div class="flex gap-2">
          <input
            type="email"
            bind:value={shareEmail}
            placeholder="输入用户邮箱 Enter email"
            class="flex-1 px-4 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onclick={() => handleShare(false)}
            disabled={shareLoading}
            class="px-4 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600 disabled:opacity-50"
          >
            分享 Share
          </button>
        </div>
      </div>

      <div class="text-center text-gray-400 text-sm my-3">或</div>

      <!-- 公开分享 -->
      <button
        onclick={() => handleShare(true)}
        disabled={shareLoading}
        class="w-full py-3 bg-gradient-to-r from-green-500 to-emerald-600 text-white font-medium rounded-xl hover:from-green-600 hover:to-emerald-700 disabled:opacity-50"
      >
        公开分享给所有用户 Share Publicly
      </button>

      {#if shareError}
        <div
          class="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm"
        >
          {shareError}
        </div>
      {/if}

      <button
        onclick={() => (showShareDialog = false)}
        class="w-full mt-4 py-2 text-gray-500 hover:text-gray-700"
      >
        取消 Cancel
      </button>
    </div>
  </div>
{/if}
<!-- 修改密码对话框 -->
{#if showPasswordDialog}
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
  >
    <div class="bg-white rounded-2xl shadow-xl max-w-sm w-full p-6">
      <h3 class="text-xl font-bold text-gray-900 mb-4">
        修改密码 Change Password
      </h3>

      <div class="space-y-4">
        <!-- 邮箱验证码 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            邮箱验证码 Email Verification Code
          </label>
          <div class="flex gap-2">
            <input
              type="text"
              bind:value={emailCode}
              placeholder="验证码 Code"
              class="flex-1 px-4 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              onclick={handleSendCode}
              disabled={codeSending || countdown > 0}
              class="px-3 py-2 bg-blue-100 text-blue-700 text-sm font-medium rounded-xl hover:bg-blue-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
            >
              {#if countdown > 0}
                {countdown}s
              {:else if codeSending}
                Sending...
              {:else}
                发送 Send
              {/if}
            </button>
          </div>
          {#if codeSent && countdown > 0}
            <p class="text-xs text-green-600 mt-1">验证码已发送 Code sent</p>
          {/if}
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            新密码 New Password
          </label>
          <input
            type="password"
            bind:value={newPassword}
            placeholder="至少6位 At least 6 chars"
            class="w-full px-4 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {#if changePasswordError}
          <div class="text-red-500 text-sm">{changePasswordError}</div>
        {/if}

        <div class="flex gap-3 pt-2">
          <button
            onclick={() => (showPasswordDialog = false)}
            class="flex-1 py-2 text-gray-500 hover:text-gray-700 bg-gray-50 hover:bg-gray-100 rounded-xl transition-colors"
          >
            取消 Cancel
          </button>
          <button
            onclick={handleChangePassword}
            disabled={changePasswordLoading}
            class="flex-1 py-2 bg-blue-500 text-white font-medium rounded-xl hover:bg-blue-600 disabled:opacity-70 transition-colors"
          >
            {#if changePasswordLoading}
              提交中...
            {:else}
              确认修改 Confirm
            {/if}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .safe-area-top {
    padding-top: env(safe-area-inset-top, 0);
  }

  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
</style>
