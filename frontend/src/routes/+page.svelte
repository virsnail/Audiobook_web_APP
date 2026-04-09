<!--
  首页 - 书架（含标签侧边栏 + 排序 + PlayAll）
-->
<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { goto } from "$app/navigation";
  import { authStore } from "$lib/stores/auth.svelte.ts";
  import {
    getBooks,
    updateBook,
    deleteBook,
    shareBook,
    getBookShares,
    unshareBook,
    changePassword,
    sendEmailCode,
    logout,
    logActivity,
    getTags,
    createTag,
    updateTag,
    deleteTag,
    updateBookTags,
    type Book,
    type Tag,
  } from "$lib/utils/api";

  // 书籍列表
  let books = $state<Book[]>([]);
  let isLoading = $state(true);
  let error = $state("");

  // 标签
  let tags = $state<Tag[]>([]);
  let selectedTagIds = $state<Set<string>>(new Set());
  let newTagName = $state("");
  let tagSearchQuery = $state("");
  let showTagInput = $state(false);
  let editingTagId = $state("");
  let editingTagName = $state("");

  // 排序
  let sortBy = $state("");

  // 侧边栏
  let sidebarWidth = $state(240);
  let isResizing = $state(false);
  let sidebarCollapsed = $state(false);

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
  let emailCode = $state("");
  let changePasswordLoading = $state(false);
  let changePasswordError = $state("");
  let codeSent = $state(false);
  let codeSending = $state(false);
  let countdown = $state(0);

  // 修改书名
  let showEditTitleDialog = $state(false);
  let editTitleBookId = $state("");
  let editTitleValue = $state("");
  let editTitleLoading = $state(false);
  let editTitleError = $state("");

  // 编辑标签对话框
  let showTagEditDialog = $state(false);
  let tagEditBookId = $state("");
  let tagEditBookTitle = $state("");
  let tagEditSelectedIds = $state<Set<string>>(new Set());
  let tagEditNewName = $state("");
  let tagEditSearchQuery = $state(""); // 对话框内标签搜索

  // 初始化
  onMount(async () => {
    await init();
  });

  // 组件销毁时清理定时器
  onDestroy(() => {
    if (_countdownTimer) {
      clearInterval(_countdownTimer);
      _countdownTimer = null;
    }
  });

  async function init() {
    isLoading = true;
    try {
      if (authStore.isLoggedIn) {
        await Promise.all([loadBooks(), loadTags()]);
      }
    } catch (e) {
      console.error("Init failed", e);
    } finally {
      isLoading = false;
    }
  }

  // 加载书籍
  async function loadBooks() {
    try {
      const tagIdsArray = selectedTagIds.size > 0 ? [...selectedTagIds] : undefined;
      const res = await getBooks({
        tag_ids: tagIdsArray,
        sort_by: sortBy || undefined,
      });
      books = res.books;
      error = "";
    } catch (err) {
      console.error("Load books failed", err);
    }
  }

  // 加载标签
  async function loadTags() {
    try {
      tags = await getTags();
    } catch (err) {
      console.error("Load tags failed", err);
    }
  }

  // 筛选后的书籍 (前端二次过滤无需，因为后端已处理)
  let displayedBooks = $derived(() => {
    let result = [...books];
    
    // 前端排序（用于即时响应，后端排序作为默认）
    if (sortBy) {
      const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
      switch (sortBy) {
        case 'title_asc':
          result.sort((a, b) => collator.compare(a.title, b.title));
          break;
        case 'title_desc':
          result.sort((a, b) => collator.compare(b.title, a.title));
          break;
        case 'created_asc':
          result.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
          break;
        case 'created_desc':
          result.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
          break;
        case 'duration_asc':
          result.sort((a, b) => (a.total_duration || 0) - (b.total_duration || 0));
          break;
        case 'duration_desc':
          result.sort((a, b) => (b.total_duration || 0) - (a.total_duration || 0));
          break;
      }
    }
    return result;
  });

  // 标签筛选
  function toggleTagFilter(tagId: string) {
    const newSet = new Set(selectedTagIds);
    if (newSet.has(tagId)) {
      newSet.delete(tagId);
    } else {
      newSet.add(tagId);
    }
    selectedTagIds = newSet;
    loadBooks();
  }

  function clearTagFilter() {
    selectedTagIds = new Set();
    loadBooks();
  }

  // 过滤后的标签（搜索）
  let filteredTags = $derived(
    tagSearchQuery
      ? tags.filter(t => t.name.toLowerCase().includes(tagSearchQuery.toLowerCase()))
      : tags
  );

  // 排序变更
  function handleSortChange(newSort: string) {
    sortBy = sortBy === newSort ? "" : newSort;
    loadBooks();
  }

  // 创建标签
  async function handleCreateTag() {
    const name = newTagName.trim();
    if (!name) return;
    try {
      await createTag(name);
      newTagName = "";
      showTagInput = false;
      await loadTags();
    } catch (e) {
      alert(e instanceof Error ? e.message : "创建标签失败");
    }
  }

  // 编辑标签名
  function startEditTag(tag: Tag) {
    editingTagId = tag.id;
    editingTagName = tag.name;
  }

  async function saveEditTag() {
    if (!editingTagId || !editingTagName.trim()) return;
    try {
      await updateTag(editingTagId, editingTagName.trim());
      editingTagId = "";
      editingTagName = "";
      await Promise.all([loadTags(), loadBooks()]);
    } catch (e) {
      alert(e instanceof Error ? e.message : "修改标签失败");
    }
  }

  function cancelEditTag() {
    editingTagId = "";
    editingTagName = "";
  }

  // 删除标签（需要二次确认）
  async function handleDeleteTag(tagId: string, tagName: string) {
    const firstConfirm = confirm(`确定要删除标签「${tagName}」吗？\nDelete tag "${tagName}"?`);
    if (!firstConfirm) return;
    const secondConfirm = confirm(`⚠️ 再次确认：删除标签「${tagName}」将从所有书籍中移除此标签。\n此操作不可撤销！\n\nConfirm: Delete tag "${tagName}"?`);
    if (!secondConfirm) return;
    try {
      await deleteTag(tagId);
      selectedTagIds.delete(tagId);
      selectedTagIds = new Set(selectedTagIds);
      await Promise.all([loadTags(), loadBooks()]);
    } catch (e) {
      alert(e instanceof Error ? e.message : "删除标签失败");
    }
  }

  // 打开编辑书籍标签对话框
  function openTagEditDialog(book: Book) {
    tagEditBookId = book.id;
    tagEditBookTitle = book.title;
    tagEditSelectedIds = new Set((book.tags || []).map(t => t.id));
    tagEditNewName = "";
    tagEditSearchQuery = ""; // 每次打开时清空搜索词
    showTagEditDialog = true;
  }

  // 在标签编辑对话框中切换标签
  function toggleBookTag(tagId: string) {
    const newSet = new Set(tagEditSelectedIds);
    if (newSet.has(tagId)) {
      newSet.delete(tagId);
    } else {
      newSet.add(tagId);
    }
    tagEditSelectedIds = newSet;
  }

  // 在标签编辑对话框中创建新标签
  async function handleCreateTagInDialog() {
    const name = tagEditNewName.trim();
    if (!name) return;
    try {
      const newTag = await createTag(name);
      tagEditNewName = "";
      await loadTags();
      // 自动勾选新创建的标签
      const newSet = new Set(tagEditSelectedIds);
      newSet.add(newTag.id);
      tagEditSelectedIds = newSet;
    } catch (e) {
      alert(e instanceof Error ? e.message : "创建标签失败");
    }
  }

  // 保存书籍标签
  async function saveBookTags() {
    try {
      await updateBookTags(tagEditBookId, [...tagEditSelectedIds]);
      showTagEditDialog = false;
      await Promise.all([loadBooks(), loadTags()]);
    } catch (e) {
      alert(e instanceof Error ? e.message : "保存标签失败");
    }
  }

  // 侧边栏拖拽调整宽度
  function startResize(e: MouseEvent) {
    isResizing = true;
    const startX = e.clientX;
    const startWidth = sidebarWidth;

    function onMouseMove(e: MouseEvent) {
      const diff = e.clientX - startX;
      sidebarWidth = Math.max(160, Math.min(500, startWidth + diff));
    }

    function onMouseUp() {
      isResizing = false;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    }

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }

  // PlayAllVisibleBooks
  function handlePlayAll() {
    const visibleBooks = displayedBooks();
    if (visibleBooks.length === 0) {
      alert("没有可播放的书籍 No books to play");
      return;
    }
    const ids = visibleBooks.map(b => b.id);
    const firstId = ids[0];
    goto(`/reader/${firstId}?playlist=${ids.join(',')}`);
  }

  // 点击书籍
  function handleBookClick(book: Book, e: MouseEvent) {
    if ((e.target as HTMLElement).closest("button")) return;
    goto(`/reader/${book.id}`);
  }

  // 获取封面
  function getBookCover(book: Book, index: number) {
    const colors = [
      "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
      "linear-gradient(135deg, #6B8DD6 0%, #8E37D7 100%)",
      "linear-gradient(to top, #cfd9df 0%, #e2ebf0 100%)",
      "linear-gradient(120deg, #a1c4fd 0%, #c2e9fb 100%)",
    ];
    if (book.cover_path) {
      const token = authStore.token || '';
      return `url('/api/books/${book.id}/cover?token=${token}')`;
    }
    return colors[index % colors.length];
  }

  // 删除书籍
  async function handleDelete(id: string) {
    if (
      !confirm("确定要删除这本书吗？Are you sure you want to delete this book?")
    )
      return;
    try {
      await deleteBook(id);
      await loadBooks();
    } catch (e) {
      alert("删除失败 Failed to delete");
    }
  }

  // 修改书名
  function openEditTitleDialog(book: Book) {
    editTitleBookId = book.id;
    editTitleValue = book.title;
    editTitleError = "";
    showEditTitleDialog = true;
  }

  async function handleSaveEditTitle() {
    const title = editTitleValue.trim();
    if (!title) {
      editTitleError = "请输入书名 Please enter a title";
      return;
    }
    editTitleLoading = true;
    editTitleError = "";
    try {
      await updateBook(editTitleBookId, { title });
      await loadBooks();
      showEditTitleDialog = false;
    } catch (e) {
      editTitleError = e instanceof Error ? e.message : "修改失败 Failed to update";
    } finally {
      editTitleLoading = false;
    }
  }

  // 分享相关
  async function openShareDialog(id: string) {
    shareBookId = id;
    shareEmail = "";
    shareError = "";
    shareStatus = null;
    showShareDialog = true;
    await loadShareStatus();
  }

  async function loadShareStatus() {
    shareStatusLoading = true;
    try {
      shareStatus = await getBookShares(shareBookId);
    } catch (e) {
      console.error(e);
    } finally {
      shareStatusLoading = false;
    }
  }

  async function handleShare(isPublic: boolean) {
    if (!isPublic && !shareEmail) return;
    shareLoading = true;
    shareError = "";
    try {
      await shareBook(shareBookId, isPublic ? undefined : shareEmail);
      await loadShareStatus();
      if (!isPublic) shareEmail = "";
      alert("分享成功 Shared successfully");
    } catch (e) {
      shareError = e instanceof Error ? e.message : "分享失败 Share failed";
    } finally {
      shareLoading = false;
    }
  }

  async function handleUnshare() {
    if (!confirm("确定要取消所有分享吗？Unshare all?")) return;
    shareLoading = true;
    try {
      await unshareBook(shareBookId);
      await loadShareStatus();
    } catch (e) {
      alert("取消分享失败 Failed to unshare");
    } finally {
      shareLoading = false;
    }
  }

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

  // 倒计时逻辑（组件销毁时自动清理）
  let _countdownTimer: ReturnType<typeof setInterval> | null = null;
  function startCountdown() {
    countdown = 60;
    if (_countdownTimer) clearInterval(_countdownTimer);
    _countdownTimer = setInterval(() => {
      countdown--;
      if (countdown <= 0) {
        clearInterval(_countdownTimer!);
        _countdownTimer = null;
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
      await changePassword(newPassword, emailCode);
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

  // 退出登录
  async function handleLogout() {
    if (!confirm("确定要退出登录吗？Are you sure you want to logout?")) return;

    try {
      await logout();
    } catch (e) {
      console.error("Logout API failed", e);
    } finally {
      authStore.logout();
      goto("/login");
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
    <div class="max-w-full mx-auto px-4 py-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <h1 class="text-2xl font-bold text-gray-900">我的书架 Bookshelf</h1>

        {#if authStore.isLoggedIn && displayedBooks().length > 0}
          <!-- PlayAllVisibleBooks 按钮 -->
          <button
            onclick={handlePlayAll}
            class="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-emerald-500 to-teal-600 text-white text-sm font-medium rounded-lg hover:from-emerald-600 hover:to-teal-700 transition-all shadow-sm hover:shadow-md"
            title="按顺序播放当前显示的所有书籍 Play all visible books in order"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
            <span class="hidden sm:inline">播放全部 PlayAll</span>
            <span class="text-xs opacity-80">({displayedBooks().length})</span>
          </button>
        {/if}
      </div>

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

  <!-- 主内容区域 -->
  <main class="flex" style="min-height: calc(100vh - 73px);">
    {#if isLoading}
      <div class="flex-1 flex items-center justify-center py-20">
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
      <div class="flex-1 p-4">
        <div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600">
          {error}
        </div>
      </div>
    {:else if authStore.isLoggedIn}
      <!-- 左侧标签侧边栏 -->
      <aside
        class="sidebar bg-white border-r border-gray-200 flex-shrink-0 overflow-hidden flex flex-col"
        style="width: {sidebarCollapsed ? 40 : sidebarWidth}px;"
      >
        {#if sidebarCollapsed}
          <button
            class="p-2 m-1 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            onclick={() => sidebarCollapsed = false}
            title="展开侧边栏 Expand"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M9 5l7 7-7 7" />
            </svg>
          </button>
        {:else}
          <!-- 侧边栏标题 -->
          <div class="px-3 py-3 border-b border-gray-100 flex items-center justify-between">
            <h2 class="text-sm font-bold text-gray-700 flex items-center gap-1.5">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
              </svg>
              标签 Tags
            </h2>
            <div class="flex items-center gap-1">
              <!-- 新建标签按钮（+号，移到这里） -->
              {#if showTagInput}
                <div class="flex gap-1">
                  <input
                    type="text"
                    bind:value={newTagName}
                    placeholder="标签名"
                    class="w-20 px-1.5 py-0.5 text-xs border border-blue-300 rounded focus:ring-1 focus:ring-blue-400"
                    onkeydown={(e) => { if (e.key === 'Enter') handleCreateTag(); if (e.key === 'Escape') { showTagInput = false; newTagName = ''; } }}
                  />
                  <button
                    onclick={handleCreateTag}
                    class="px-1.5 py-0.5 bg-blue-500 text-white text-xs rounded hover:bg-blue-600"
                  >✓</button>
                </div>
              {:else}
                <button
                  onclick={() => showTagInput = true}
                  class="p-1 text-blue-500 hover:text-blue-700 hover:bg-blue-50 rounded transition-colors"
                  title="新建标签 New Tag"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                  </svg>
                </button>
              {/if}
              <!-- 收起按钮 -->
              <button
                class="p-1 text-gray-400 hover:text-gray-600 rounded"
                onclick={() => sidebarCollapsed = true}
                title="收起 Collapse"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M15 19l-7-7 7-7" />
                </svg>
              </button>
            </div>
          </div>

          <!-- 搜索标签 -->
          <div class="px-3 py-2">
            <input
              type="text"
              bind:value={tagSearchQuery}
              placeholder="搜索标签 Search tags..."
              class="w-full px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg focus:ring-1 focus:ring-blue-400 focus:border-blue-400 bg-gray-50"
            />
          </div>

          <!-- 标签列表 -->
          <div class="flex-1 overflow-y-auto px-2 py-1">
            <!-- 全部 -->
            <button
              class="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm transition-colors {selectedTagIds.size === 0 ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-50'}"
              onclick={clearTagFilter}
            >
              <span class="w-4 h-4 flex items-center justify-center">
                {#if selectedTagIds.size === 0}
                  <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                  </svg>
                {/if}
              </span>
              全部 All
              <span class="ml-auto text-xs text-gray-400">{books.length}</span>
            </button>

            {#each filteredTags as tag}
              <div class="group flex items-center gap-1">
                {#if editingTagId === tag.id}
                  <div class="flex-1 flex items-center gap-1 py-1 px-2">
                    <input
                      type="text"
                      bind:value={editingTagName}
                      class="flex-1 min-w-0 px-1.5 py-0.5 text-sm border border-blue-300 rounded focus:ring-1 focus:ring-blue-400"
                      onkeydown={(e) => { if (e.key === 'Enter') saveEditTag(); if (e.key === 'Escape') cancelEditTag(); }}
                    />
                    <button onclick={saveEditTag} class="text-blue-500 hover:text-blue-700 p-0.5" title="保存">✓</button>
                    <button onclick={cancelEditTag} class="text-gray-400 hover:text-gray-600 p-0.5" title="取消">✕</button>
                  </div>
                {:else}
                  <button
                    class="flex-1 flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm transition-colors {selectedTagIds.has(tag.id) ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-50'}"
                    onclick={() => toggleTagFilter(tag.id)}
                  >
                    <span class="w-4 h-4 flex items-center justify-center flex-shrink-0">
                      {#if selectedTagIds.has(tag.id)}
                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                        </svg>
                      {/if}
                    </span>
                    <span class="truncate">{tag.name}</span>
                    <span class="ml-auto text-xs text-gray-400 flex-shrink-0">{tag.book_count}</span>
                  </button>
                  <!-- 编辑/删除（仅自己的标签） -->
                  {#if tag.owner_id === authStore.user?.id}
                    <div class="hidden group-hover:flex items-center gap-0.5 flex-shrink-0">
                      <button
                        onclick={() => startEditTag(tag)}
                        class="p-1 text-gray-400 hover:text-amber-500 rounded"
                        title="修改 Edit"
                      >
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                        </svg>
                      </button>
                      <button
                        onclick={() => handleDeleteTag(tag.id, tag.name)}
                        class="p-1 text-gray-400 hover:text-red-500 rounded"
                        title="删除 Delete"
                      >
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  {/if}
                {/if}
              </div>
            {/each}
          <!-- 标签列表结束，底部无需新建按钮 -->
          </div>

        {/if}
      </aside>

      <!-- 拖拽把手 -->
      {#if !sidebarCollapsed}
        <div
          class="resize-handle"
          onmousedown={startResize}
          role="separator"
          aria-label="Resize sidebar"
          tabindex="-1"
        ></div>
      {/if}

      <!-- 右侧书籍区域 -->
      <div class="flex-1 overflow-auto">
        <!-- 排序控制栏 -->
        <div class="sticky top-0 bg-gray-50/90 backdrop-blur-sm border-b border-gray-100 px-4 py-2 flex items-center gap-2 z-[5] flex-wrap">
          <span class="text-xs text-gray-500 mr-1">排序 Sort:</span>
          {#each [
            { key: 'title_asc', label: '名称↑ A-Z' },
            { key: 'title_desc', label: '名称↓ Z-A' },
            { key: 'created_desc', label: '最新 Newest' },
            { key: 'created_asc', label: '最早 Oldest' },
            { key: 'duration_desc', label: '最长 Longest' },
            { key: 'duration_asc', label: '最短 Shortest' },
          ] as opt}
            <button
              class="px-2 py-1 text-xs rounded-md transition-colors {sortBy === opt.key ? 'bg-blue-500 text-white shadow-sm' : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'}"
              onclick={() => handleSortChange(opt.key)}
            >
              {opt.label}
            </button>
          {/each}
        </div>

        <!-- 书籍网格 -->
        <div class="px-4 py-4">
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {#each displayedBooks() as book, i}
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
                  <!-- 标签 chips -->
                  {#if book.tags && book.tags.length > 0}
                    <div class="flex flex-wrap gap-1 mb-2">
                      {#each book.tags as tag}
                        <span class="inline-flex items-center px-2 py-0.5 text-xs rounded-full bg-blue-50 text-blue-600 border border-blue-100">
                          {tag.name}
                        </span>
                      {/each}
                    </div>
                  {/if}

                  <p class="text-gray-500 text-sm line-clamp-2">
                    {book.description || "暂无简介 No Description"}
                  </p>

                  <!-- 操作按钮 -->
                  <div class="mt-3 flex items-start justify-between gap-2 flex-wrap">
                    <div class="flex items-center gap-2">
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
                      <!-- 非自己的书显示来源标签 -->
                      {#if book.owner_id !== authStore.user?.id}
                        <span class="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                          {book.is_public ? '公开 Public' : '分享 Shared'}
                        </span>
                      {/if}
                    </div>

                    <!-- 操作按钮区域 - 始终可见，hover 时高亮 -->
                    {#if book.owner_id === authStore.user?.id}
                      <div class="flex items-center gap-1.5">
                        <!-- 编辑标签 -->
                        <button
                          onclick={() => openTagEditDialog(book)}
                          class="flex items-center gap-1 px-2 py-1.5 text-xs text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors border border-gray-200 hover:border-blue-200"
                          title="编辑标签 Edit Tags"
                        >
                          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                          </svg>
                          <span class="hidden sm:inline">标签</span>
                        </button>
                        <!-- 修改书名 -->
                        <button
                          onclick={() => openEditTitleDialog(book)}
                          class="flex items-center gap-1 px-2 py-1.5 text-xs text-gray-500 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors border border-gray-200 hover:border-amber-200"
                          title="修改书名 Edit Title"
                        >
                          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                          </svg>
                          <span class="hidden sm:inline">改名</span>
                        </button>
                        <!-- 分享按钮 -->
                        <button
                          onclick={() => openShareDialog(book.id)}
                          class="flex items-center gap-1 px-2 py-1.5 text-xs text-gray-500 hover:text-blue-500 hover:bg-blue-50 rounded-lg transition-colors border border-gray-200 hover:border-blue-200"
                          title="分享 Share"
                        >
                          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                          </svg>
                          <span class="hidden sm:inline">分享</span>
                        </button>
                        <!-- 删除按钮 -->
                        <button
                          onclick={() => handleDelete(book.id)}
                          class="flex items-center gap-1 px-2 py-1.5 text-xs text-gray-500 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors border border-gray-200 hover:border-red-200"
                          title="删除 Delete"
                        >
                          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                          <span class="hidden sm:inline">删除</span>
                        </button>
                      </div>
                    {/if}
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
                {#if selectedTagIds.size > 0}
                  <h3 class="text-lg font-medium text-gray-900">
                    没有匹配的书籍 No matching books
                  </h3>
                  <p class="text-gray-500 mt-1">
                    尝试选择其他标签 Try other tags
                  </p>
                  <button
                    onclick={clearTagFilter}
                    class="mt-4 px-4 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600 transition-colors"
                  >
                    清除筛选 Clear Filter
                  </button>
                {:else}
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
                {/if}
              </div>
            {/each}
          </div>
        </div>
      </div>
    {:else}
      <!-- 未登录显示 Landing Page -->
      <div class="flex-1 py-16 text-center">
        <div class="max-w-3xl mx-auto px-4">
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

<!-- 编辑书籍标签对话框 -->
{#if showTagEditDialog}
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
  >
    <div class="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
      <h3 class="text-xl font-bold text-gray-900 mb-1">
        编辑标签 Edit Tags
      </h3>
      <p class="text-sm text-gray-500 mb-4 truncate">
        {tagEditBookTitle}
      </p>

      <!-- 搜索框 -->
      <div class="relative mb-2">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          type="text"
          bind:value={tagEditSearchQuery}
          placeholder="搜索标签 Search tags..."
          class="w-full pl-9 pr-3 py-2 border border-gray-200 rounded-xl text-sm focus:ring-1 focus:ring-blue-400 focus:border-blue-400 bg-gray-50"
        />
        {#if tagEditSearchQuery}
          <button
            onclick={() => tagEditSearchQuery = ""}
            class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        {/if}
      </div>

      <!-- 标签列表 (多选) -->
      <div class="max-h-52 overflow-y-auto border border-gray-100 rounded-xl p-2 mb-3 space-y-0.5">
        {#each tags.filter(t => t.owner_id === authStore.user?.id && (!tagEditSearchQuery || t.name.toLowerCase().includes(tagEditSearchQuery.toLowerCase()))) as tag}
          <label class="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-50 cursor-pointer text-sm">
            <input
              type="checkbox"
              checked={tagEditSelectedIds.has(tag.id)}
              onchange={() => toggleBookTag(tag.id)}
              class="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-400"
            />
            <!-- 高亮匹配的搜索词 -->
            {#if tagEditSearchQuery}
              {@const lower = tag.name.toLowerCase()}
              {@const idx = lower.indexOf(tagEditSearchQuery.toLowerCase())}
              {@const before = tag.name.slice(0, idx)}
              {@const match = tag.name.slice(idx, idx + tagEditSearchQuery.length)}
              {@const after = tag.name.slice(idx + tagEditSearchQuery.length)}
              <span>{before}<mark class="bg-yellow-100 text-yellow-800 rounded px-0.5">{match}</mark>{after}</span>
            {:else}
              <span>{tag.name}</span>
            {/if}
            <span class="text-xs text-gray-400 ml-auto">{tag.book_count}</span>
          </label>
        {:else}
          <p class="text-sm text-gray-400 px-2 py-3 text-center">
            {tagEditSearchQuery ? `没有匹配「${tagEditSearchQuery}」的标签 No matching tags` : '暂无标签，请先创建 No tags yet'}
          </p>
        {/each}
      </div>

      <!-- 快速创建新标签 -->
      <div class="flex gap-2 mb-4">
        <input
          type="text"
          bind:value={tagEditNewName}
          placeholder="新标签名 New tag name"
          class="flex-1 px-3 py-2 border border-gray-200 rounded-xl text-sm focus:ring-1 focus:ring-blue-400 focus:border-blue-400"
          onkeydown={(e) => { if (e.key === 'Enter') handleCreateTagInDialog(); }}
        />
        <button
          onclick={handleCreateTagInDialog}
          disabled={!tagEditNewName.trim()}
          class="px-3 py-2 bg-blue-500 text-white text-sm rounded-xl hover:bg-blue-600 disabled:opacity-50 transition-colors"
        >
          创建 Create
        </button>
      </div>

      <div class="flex gap-3">
        <button
          onclick={() => showTagEditDialog = false}
          class="flex-1 py-2.5 text-gray-600 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors"
        >
          取消 Cancel
        </button>
        <button
          onclick={saveBookTags}
          class="flex-1 py-2.5 bg-blue-500 text-white font-medium rounded-xl hover:bg-blue-600 transition-colors"
        >
          保存 Save
        </button>
      </div>
    </div>
  </div>
{/if}

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

<!-- 修改书名对话框 -->
{#if showEditTitleDialog}
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
  >
    <div class="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
      <h3 class="text-xl font-bold text-gray-900 mb-4">
        修改书名 Edit Title
      </h3>
      <input
        type="text"
        bind:value={editTitleValue}
        placeholder="书名 Book title"
        class="w-full px-4 py-3 border border-gray-200 rounded-xl bg-white text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent mb-4"
      />
      {#if editTitleError}
        <p class="text-red-500 text-sm mb-3">{editTitleError}</p>
      {/if}
      <div class="flex gap-3">
        <button
          onclick={() => (showEditTitleDialog = false)}
          class="flex-1 py-2.5 text-gray-600 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors"
        >
          取消 Cancel
        </button>
        <button
          onclick={handleSaveEditTitle}
          disabled={editTitleLoading}
          class="flex-1 py-2.5 bg-blue-500 text-white font-medium rounded-xl hover:bg-blue-600 disabled:opacity-50 transition-colors"
        >
          {#if editTitleLoading}
            保存中...
          {:else}
            保存 Save
          {/if}
        </button>
      </div>
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

  .sidebar {
    transition: width 0.2s ease;
  }

  .resize-handle {
    width: 4px;
    cursor: col-resize;
    background: transparent;
    transition: background 0.15s;
    flex-shrink: 0;
  }

  .resize-handle:hover,
  .resize-handle:active {
    background: #3b82f6;
  }
</style>
