<!--
  登录页面
-->
<script lang="ts">
  import { goto } from "$app/navigation";
  import { authStore } from "$lib/stores/auth.svelte";
  import { login, getMe } from "$lib/utils/api";

  let email = $state("");
  let password = $state("");
  let error = $state("");
  let isLoading = $state(false);

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = "";
    isLoading = true;

    try {
      // 登录获取 token
      const { access_token } = await login(email, password);

      // 临时设置 token 以获取用户信息
      authStore.login(access_token, {
        id: "",
        email: "",
        nickname: "",
        is_admin: false,
      });

      // 获取用户信息
      const user = await getMe();
      authStore.login(access_token, user);

      // 跳转到首页
      goto("/");
    } catch (err) {
      error = err instanceof Error ? err.message : "登录失败";
    } finally {
      isLoading = false;
    }
  }
</script>

<svelte:head>
  <title>登录 Login - AudioBook</title>
</svelte:head>

<div
  class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 px-4"
>
  <div class="max-w-md w-full">
    <!-- Logo -->
    <div class="text-center mb-8">
      <div
        class="w-16 h-16 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl mx-auto mb-4 flex items-center justify-center shadow-lg"
      >
        <svg
          class="w-8 h-8 text-white"
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
      <h1 class="text-2xl font-bold text-gray-900">AudioBook Reader</h1>
      <p class="text-gray-500 mt-1">登录你的账户 Login to your account</p>
    </div>

    <!-- 登录表单 -->
    <div class="bg-white rounded-2xl shadow-xl p-8">
      <form onsubmit={handleSubmit} class="space-y-5">
        <!-- 邮箱 -->
        <div>
          <label
            for="email"
            class="block text-sm font-medium text-gray-700 mb-1"
          >
            邮箱 Email
          </label>
          <input
            id="email"
            type="email"
            bind:value={email}
            required
            autocomplete="email"
            class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            placeholder="your@email.com"
          />
        </div>

        <!-- 密码 -->
        <div>
          <label
            for="password"
            class="block text-sm font-medium text-gray-700 mb-1"
          >
            密码 Password
          </label>
          <input
            id="password"
            type="password"
            bind:value={password}
            required
            autocomplete="current-password"
            class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            placeholder="••••••••"
          />
        </div>

        <!-- 错误信息 -->
        {#if error}
          <div
            class="p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm"
          >
            {error}
          </div>
        {/if}

        <!-- 登录按钮 -->
        <button
          type="submit"
          disabled={isLoading}
          class="w-full py-3 px-4 bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-medium rounded-xl hover:from-blue-600 hover:to-indigo-700 focus:ring-4 focus:ring-blue-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
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
              登录中... Logging in...
            </span>
          {:else}
            登录 Login
          {/if}
        </button>
      </form>

      <!-- 注册链接 -->
      <div class="mt-6 text-center">
        <p class="text-gray-500 text-sm">
          还没有账户？ No account?
          <a
            href="/register"
            class="text-blue-600 hover:text-blue-700 font-medium"
          >
            立即注册 Register Now
          </a>
        </p>
      </div>
    </div>
  </div>
</div>
