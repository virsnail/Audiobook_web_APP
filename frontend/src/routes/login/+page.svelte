<!--
  登录页面
  含：登录表单 + 忘记密码功能
-->
<script lang="ts">
  import { goto } from "$app/navigation";
  import { onDestroy } from "svelte";
  import { authStore } from "$lib/stores/auth.svelte.ts";
  import { login, getMe, sendEmailCode, forgotPassword } from "$lib/utils/api";

  // ========== 登录状态 ==========
  let email = $state("");
  let password = $state("");
  let error = $state("");
  let isLoading = $state(false);
  let isLockedOut = $state(false); // 登录次数达到上限

  // ========== 忘记密码状态 ==========
  let showForgotPassword = $state(false);
  let fpEmail = $state("");
  let fpCode = $state("");
  let fpNewPassword = $state("");
  let fpConfirmPassword = $state("");
  let fpError = $state("");
  let fpSuccess = $state("");
  let fpIsLoading = $state(false);
  let fpCodeSent = $state(false);
  let fpCodeSending = $state(false);
  let fpCountdown = $state(0);
  let _fpTimer: ReturnType<typeof setInterval> | null = null;

  onDestroy(() => {
    if (_fpTimer) {
      clearInterval(_fpTimer);
      _fpTimer = null;
    }
  });

  // ========== 登录 ==========
  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (isLockedOut) return;
    error = "";
    isLoading = true;

    try {
      const { access_token } = await login(email, password);

      authStore.login(access_token, {
        id: "",
        email: "",
        nickname: "",
        is_admin: false,
      });

      const user = await getMe();
      authStore.login(access_token, user);

      goto("/");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "登录失败";
      error = msg;
      // 检测是否为次数达到上限
      if (msg.includes("上限") || msg.includes("请明天再试")) {
        isLockedOut = true;
      }
    } finally {
      isLoading = false;
    }
  }

  // ========== 忘记密码 ==========
  function openForgotPassword() {
    showForgotPassword = true;
    fpEmail = email; // 预填登录页的邮箱
    fpError = "";
    fpSuccess = "";
  }

  async function handleSendFpCode() {
    if (!fpEmail) {
      fpError = "请输入邮箱 Please enter your email";
      return;
    }
    fpError = "";
    fpCodeSending = true;

    try {
      const result = await sendEmailCode(fpEmail);
      fpCodeSent = true;
      // 开发模式自动填充验证码
      if (result.message.includes("开发模式")) {
        const match = result.message.match(/: (\d{6})/);
        if (match) fpCode = match[1];
      }
      // 倒计时
      fpCountdown = 60;
      if (_fpTimer) clearInterval(_fpTimer);
      _fpTimer = setInterval(() => {
        fpCountdown--;
        if (fpCountdown <= 0) {
          clearInterval(_fpTimer!);
          _fpTimer = null;
        }
      }, 1000);
    } catch (err) {
      fpError = err instanceof Error ? err.message : "发送验证码失败";
    } finally {
      fpCodeSending = false;
    }
  }

  async function handleForgotPassword() {
    fpError = "";
    fpSuccess = "";

    if (!fpEmail) {
      fpError = "请输入邮箱";
      return;
    }
    if (!fpCode || fpCode.length !== 6) {
      fpError = "请输入 6 位验证码";
      return;
    }
    if (!fpNewPassword || fpNewPassword.length < 6) {
      fpError = "密码长度至少 6 位";
      return;
    }
    if (fpNewPassword !== fpConfirmPassword) {
      fpError = "两次输入的密码不一致";
      return;
    }

    fpIsLoading = true;
    try {
      const result = await forgotPassword(fpEmail, fpCode, fpNewPassword);
      fpSuccess = result.message || "密码重置成功，请使用新密码登录";
      // 重置登录锁定状态
      isLockedOut = false;
      error = "";
      // 预填邮箱到登录表单
      email = fpEmail;
      password = "";
    } catch (err) {
      const msg = err instanceof Error ? err.message : "重置密码失败";
      fpError = msg;
    } finally {
      fpIsLoading = false;
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
    {#if !showForgotPassword}
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
              disabled={isLockedOut}
              autocomplete="email"
              class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all disabled:opacity-50 disabled:bg-gray-50"
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
              disabled={isLockedOut}
              autocomplete="current-password"
              class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all disabled:opacity-50 disabled:bg-gray-50"
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

          <!-- 登录次数锁定提示 -->
          {#if isLockedOut}
            <div
              class="p-3 bg-orange-50 border border-orange-200 rounded-xl text-orange-700 text-sm"
            >
              <strong>登录已锁定</strong>：今日尝试次数已达上限，请明天再试。
              <br />
              如需立即使用，请通过下方「忘记密码」重置密码。
            </div>
          {/if}

          <!-- 登录按钮 -->
          <button
            type="submit"
            disabled={isLoading || isLockedOut}
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

        <!-- 忘记密码 & 注册链接 -->
        <div class="mt-6 space-y-3 text-center">
          <button
            onclick={openForgotPassword}
            class="text-sm text-blue-600 hover:text-blue-700 font-medium cursor-pointer"
          >
            忘记密码？Forgot Password?
          </button>
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

    <!-- 忘记密码表单 -->
    {:else}
      <div class="bg-white rounded-2xl shadow-xl p-8">
        <h2 class="text-lg font-bold text-gray-900 mb-1">
          找回密码 Reset Password
        </h2>
        <p class="text-sm text-gray-500 mb-5">
          通过邮箱验证码重置密码
        </p>

        <div class="space-y-4">
          <!-- 邮箱 -->
          <div>
            <label
              for="fp-email"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              注册邮箱 Email
            </label>
            <input
              id="fp-email"
              type="email"
              bind:value={fpEmail}
              required
              class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              placeholder="your@email.com"
            />
          </div>

          <!-- 验证码 -->
          <div>
            <label
              for="fp-code"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              邮箱验证码 Verification Code
            </label>
            <div class="flex gap-2">
              <input
                id="fp-code"
                type="text"
                bind:value={fpCode}
                maxlength="6"
                required
                class="flex-1 px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                placeholder="6 位验证码"
              />
              <button
                type="button"
                onclick={handleSendFpCode}
                disabled={fpCodeSending || fpCountdown > 0}
                class="px-4 py-3 bg-blue-100 text-blue-700 font-medium rounded-xl hover:bg-blue-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap text-sm"
              >
                {#if fpCountdown > 0}
                  {fpCountdown}s
                {:else if fpCodeSending}
                  发送中...
                {:else}
                  发送验证码
                {/if}
              </button>
            </div>
          </div>

          <!-- 新密码 -->
          <div>
            <label
              for="fp-password"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              新密码 New Password
            </label>
            <input
              id="fp-password"
              type="password"
              bind:value={fpNewPassword}
              required
              autocomplete="new-password"
              class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              placeholder="至少 6 位"
            />
          </div>

          <!-- 确认密码 -->
          <div>
            <label
              for="fp-confirm"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              确认密码 Confirm Password
            </label>
            <input
              id="fp-confirm"
              type="password"
              bind:value={fpConfirmPassword}
              required
              autocomplete="new-password"
              class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              placeholder="再次输入新密码"
            />
          </div>

          <!-- 错误信息 -->
          {#if fpError}
            <div
              class="p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm"
            >
              {fpError}
            </div>
          {/if}

          <!-- 成功信息 -->
          {#if fpSuccess}
            <div
              class="p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm"
            >
              {fpSuccess}
            </div>
          {/if}

          <!-- 重置密码按钮 -->
          <button
            type="button"
            onclick={handleForgotPassword}
            disabled={fpIsLoading || !!fpSuccess}
            class="w-full py-3 px-4 bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-medium rounded-xl hover:from-blue-600 hover:to-indigo-700 focus:ring-4 focus:ring-blue-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {#if fpIsLoading}
              重置中... Resetting...
            {:else}
              重置密码 Reset Password
            {/if}
          </button>

          <!-- 返回登录 -->
          <button
            type="button"
            onclick={() => { showForgotPassword = false; }}
            class="w-full py-3 px-4 border border-gray-200 text-gray-700 font-medium rounded-xl hover:bg-gray-50 transition-all"
          >
            返回登录 Back to Login
          </button>
        </div>
      </div>
    {/if}
  </div>
</div>
