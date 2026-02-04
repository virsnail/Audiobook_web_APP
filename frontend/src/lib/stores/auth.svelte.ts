/**
 * 认证状态管理
 * 使用 Svelte 5 runes
 */

import { browser } from '$app/environment';

// Token 存储键
const TOKEN_KEY = 'audiobook_token';
const USER_KEY = 'audiobook_user';

// 用户信息类型
export interface User {
  id: string;
  email: string;
  nickname: string;
  is_admin: boolean;
}

// 状态
let token = $state<string | null>(null);
let user = $state<User | null>(null);
let isLoading = $state(true);

// 初始化：从 localStorage 恢复状态
function init() {
  if (browser) {
    const savedToken = localStorage.getItem(TOKEN_KEY);
    const savedUser = localStorage.getItem(USER_KEY);
    
    if (savedToken) {
      token = savedToken;
    }
    if (savedUser) {
      try {
        user = JSON.parse(savedUser);
      } catch {
        user = null;
      }
    }
    isLoading = false;
  }
}

// 登录
function login(accessToken: string, userData: User) {
  token = accessToken;
  user = userData;
  
  if (browser) {
    localStorage.setItem(TOKEN_KEY, accessToken);
    localStorage.setItem(USER_KEY, JSON.stringify(userData));
  }
}

// 登出
function logout() {
  token = null;
  user = null;
  
  if (browser) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }
}

// 更新用户信息
function updateUser(userData: User) {
  user = userData;
  
  if (browser) {
    localStorage.setItem(USER_KEY, JSON.stringify(userData));
  }
}

// 获取 Authorization header
function getAuthHeader(): Record<string, string> {
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

// 初始化
init();

// 导出 store
export const authStore = {
  // 状态
  get token() { return token; },
  get user() { return user; },
  get isLoading() { return isLoading; },
  get isLoggedIn() { return !!token && !!user; },
  
  // 方法
  login,
  logout,
  updateUser,
  getAuthHeader,
  init,
};
