<!--
  注册页面
  三步流程：邀请码 → 邮箱验证 → 设置密码
-->
<script lang="ts">
  import { goto } from "$app/navigation";
  import { authStore } from "$lib/stores/auth.svelte";
  import { sendEmailCode, register, getMe } from "$lib/utils/api";

  // 当前步骤
  let step = $state(1);

  // 表单数据
  let invitationCode = $state("");
  let email = $state("");
  let emailCode = $state("");
  let password = $state("");
  let confirmPassword = $state("");
  let nickname = $state("");

  // 状态
  let error = $state("");
  let isLoading = $state(false);
  let codeSent = $state(false);
  let countdown = $state(0);

  // 验证邀请码格式
  function validateInvitationCode(): boolean {
    if (!invitationCode.trim()) {
      error = "请输入邀请码";
      return false;
    }
    return true;
  }

  // 进入下一步
  function goToStep2() {
    if (validateInvitationCode()) {
      error = "";
      step = 2;
    }
  }

  // 发送验证码
  async function handleSendCode() {
    if (!email.trim() || !email.includes("@")) {
      error = "请输入有效的邮箱地址";
      return;
    }

    error = "";
    isLoading = true;

    try {
      const result = await sendEmailCode(email);
      codeSent = true;

      // 开发模式下显示验证码
      if (result.message.includes("开发模式")) {
        const match = result.message.match(/: (\d{6})/);
        if (match) {
          emailCode = match[1];
        }
      }

      // 倒计时
      countdown = 60;
      const timer = setInterval(() => {
        countdown--;
        if (countdown <= 0) {
          clearInterval(timer);
        }
      }, 1000);
    } catch (err) {
      error = err instanceof Error ? err.message : "发送验证码失败";
    } finally {
      isLoading = false;
    }
  }

  // 验证邮箱验证码
  function goToStep3() {
    if (!emailCode.trim() || emailCode.length !== 6) {
      error = "请输入6位验证码";
      return;
    }
    error = "";
    step = 3;
  }

  // 完成注册
  async function handleRegister(e: Event) {
    e.preventDefault();

    if (password.length < 6) {
      error = "密码至少6位";
      return;
    }

    if (password !== confirmPassword) {
      error = "两次密码不一致";
      return;
    }

    error = "";
    isLoading = true;

    try {
      const { access_token } = await register({
        email,
        password,
        nickname: nickname || undefined,
        invitation_code: invitationCode,
        email_code: emailCode,
      });

      // 获取用户信息并登录
      authStore.login(access_token, {
        id: "",
        email: "",
        nickname: "",
        is_admin: false,
      });
      const user = await getMe();
      authStore.login(access_token, user);

      // 跳转到首页
      goto("/");
    } catch (err) {
      error = err instanceof Error ? err.message : "注册失败";
    } finally {
      isLoading = false;
    }
  }
</script>

<svelte:head>
  <title>注册 Register - AudioBook</title>
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
      <p class="text-gray-500 mt-1">创建新账户 Create New Account</p>
    </div>

    <!-- 步骤指示器 -->
    <div class="flex items-center justify-center gap-2 mb-6">
      {#each [1, 2, 3] as s}
        <div class="flex items-center">
          <div
            class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium
            {step >= s
              ? 'bg-blue-500 text-white'
              : 'bg-gray-200 text-gray-500'}"
          >
            {s}
          </div>
          {#if s < 3}
            <div
              class="w-8 h-0.5 {step > s ? 'bg-blue-500' : 'bg-gray-200'}"
            ></div>
          {/if}
        </div>
      {/each}
    </div>

    <!-- 注册表单 -->
    <div class="bg-white rounded-2xl shadow-xl p-8">
      <!-- 步骤1：邀请码 -->
      {#if step === 1}
        <div class="space-y-5">
          <div class="text-center mb-4">
            <h2 class="text-lg font-semibold text-gray-900">
              输入邀请码 Enter Invitation Code
            </h2>
            <p class="text-gray-500 text-sm mt-1">
              需要邀请码才能注册 Invitation code required
            </p>
          </div>

          <div>
            <label
              for="invitation"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              邀请码 Invitation Code
            </label>
            <input
              id="invitation"
              type="text"
              bind:value={invitationCode}
              class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all font-mono tracking-wider"
              placeholder="XXXXXXXX"
            />
          </div>

          {#if error}
            <div
              class="p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm"
            >
              {error}
            </div>
          {/if}

          <button
            type="button"
            onclick={goToStep2}
            class="w-full py-3 px-4 bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-medium rounded-xl hover:from-blue-600 hover:to-indigo-700 focus:ring-4 focus:ring-blue-200 transition-all"
          >
            下一步 Next
          </button>
        </div>
      {/if}

      <!-- 步骤2：邮箱验证 -->
      {#if step === 2}
        <div class="space-y-5">
          <div class="text-center mb-4">
            <h2 class="text-lg font-semibold text-gray-900">
              验证邮箱 Verify Email
            </h2>
            <p class="text-gray-500 text-sm mt-1">
              我们会发送验证码到您的邮箱 We'll send a code to your email
            </p>
          </div>

          <div>
            <label
              for="email"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              邮箱 Email
            </label>
            <div class="flex gap-2">
              <input
                id="email"
                type="email"
                bind:value={email}
                disabled={codeSent}
                class="flex-1 px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all disabled:bg-gray-50"
                placeholder="your@email.com"
              />
              <button
                type="button"
                onclick={handleSendCode}
                disabled={isLoading || countdown > 0}
                class="px-4 py-3 bg-gray-100 text-gray-700 font-medium rounded-xl hover:bg-gray-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              >
                {countdown > 0 ? `${countdown}s` : "发送验证码 Send Code"}
              </button>
            </div>
          </div>

          {#if codeSent}
            <div>
              <label
                for="emailCode"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                验证码 Verification Code
              </label>
              <input
                id="emailCode"
                type="text"
                bind:value={emailCode}
                maxlength="6"
                class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all font-mono tracking-widest text-center text-2xl"
                placeholder="000000"
              />
            </div>
          {/if}

          {#if error}
            <div
              class="p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm"
            >
              {error}
            </div>
          {/if}

          <div class="flex gap-3">
            <button
              type="button"
              onclick={() => {
                step = 1;
                error = "";
              }}
              class="flex-1 py-3 px-4 bg-gray-100 text-gray-700 font-medium rounded-xl hover:bg-gray-200 transition-all"
            >
              上一步 Back
            </button>
            <button
              type="button"
              onclick={goToStep3}
              disabled={!codeSent || !emailCode}
              class="flex-1 py-3 px-4 bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-medium rounded-xl hover:from-blue-600 hover:to-indigo-700 focus:ring-4 focus:ring-blue-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              下一步 Next
            </button>
          </div>
        </div>
      {/if}

      <!-- 步骤3：设置密码 -->
      {#if step === 3}
        <form onsubmit={handleRegister} class="space-y-5">
          <div class="text-center mb-4">
            <h2 class="text-lg font-semibold text-gray-900">
              设置密码 Set Password
            </h2>
            <p class="text-gray-500 text-sm mt-1">
              完成注册 Complete Registration
            </p>
          </div>

          <div>
            <label
              for="nickname"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              昵称 Nickname <span class="text-gray-400">(可选 Optional)</span>
            </label>
            <input
              id="nickname"
              type="text"
              bind:value={nickname}
              class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              placeholder="你的昵称"
            />
          </div>

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
              minlength="6"
              class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              placeholder="至少6位"
            />
          </div>

          <div>
            <label
              for="confirmPassword"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              确认密码 Confirm Password
            </label>
            <input
              id="confirmPassword"
              type="password"
              bind:value={confirmPassword}
              required
              class="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              placeholder="再次输入密码"
            />
          </div>

          {#if error}
            <div
              class="p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm"
            >
              {error}
            </div>
          {/if}

          <div class="flex gap-3">
            <button
              type="button"
              onclick={() => {
                step = 2;
                error = "";
              }}
              class="flex-1 py-3 px-4 bg-gray-100 text-gray-700 font-medium rounded-xl hover:bg-gray-200 transition-all"
            >
              上一步 Back
            </button>
            <button
              type="submit"
              disabled={isLoading}
              class="flex-1 py-3 px-4 bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-medium rounded-xl hover:from-blue-600 hover:to-indigo-700 focus:ring-4 focus:ring-blue-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {#if isLoading}
                注册中... Registering...
              {:else}
                完成注册 Complete
              {/if}
            </button>
          </div>
        </form>
      {/if}

      <!-- 登录链接 -->
      <div class="mt-6 text-center">
        <p class="text-gray-500 text-sm">
          已有账户？ Already have an account?
          <a
            href="/login"
            class="text-blue-600 hover:text-blue-700 font-medium"
          >
            立即登录 Login Now
          </a>
        </p>
      </div>
    </div>
  </div>
</div>
