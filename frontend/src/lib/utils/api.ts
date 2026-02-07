/**
 * API 工具函数
 */

import { authStore } from '$lib/stores/auth.svelte.ts';
import { browser } from '$app/environment';

const API_BASE = '/api';

// 通用请求函数
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...authStore.getAuthHeader(),
    ...(options.headers as Record<string, string> || {})
  };
  
  // 如果是 FormData，不设置 Content-Type（让浏览器自动设置）
  if (options.body instanceof FormData) {
    delete headers['Content-Type'];
  }
  
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '请求失败' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  
  // 处理空响应
  const text = await response.text();
  if (!text) return {} as T;
  
  return JSON.parse(text);
}

// ============ 认证 API ============

export interface LoginResponse {
  access_token: string;
}

export interface UserResponse {
  id: string;
  email: string;
  nickname: string;
  is_admin: boolean;
}

// 发送邮箱验证码
export async function sendEmailCode(email: string): Promise<{ message: string }> {
  return request('/auth/send-code', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}

// 用户注册
export async function register(data: {
  email: string;
  password: string;
  nickname?: string;
  invitation_code: string;
  email_code: string;
}): Promise<LoginResponse> {
  return request('/auth/register', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// 用户登录
export async function login(email: string, password: string): Promise<LoginResponse> {
  return request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

// 获取当前用户信息
export async function getMe(): Promise<UserResponse> {
  return request('/auth/me');
}

// 生成邀请码（管理员）
export async function createInvitationCodes(count: number = 1): Promise<{ codes: string[] }> {
  return request(`/auth/invitation-codes?count=${count}`, {
    method: 'POST',
  });
}

// 修改密码
export async function changePassword(newPassword: string, emailCode: string): Promise<{ message: string }> {
  return request('/auth/change-password', {
    method: 'PUT',
    body: JSON.stringify({ 
      new_password: newPassword,
      email_code: emailCode
    }),
  });
}

// 退出登录
export async function logout(): Promise<{ message: string }> {
  return request('/auth/logout', {
    method: 'POST',
  });
}

// 记录前端活动
export async function logActivity(action: string, details?: Record<string, any>): Promise<void> {
  // 不等待日志记录结果，避免阻塞 UI
  request('/activity/log', {
    method: 'POST',
    body: JSON.stringify({ action, details }),
  }).catch(e => console.error('Log activity failed', e));
}


// ============ 书籍 API ============

export interface Book {
  id: string;
  title: string;
  author?: string;
  description?: string;
  cover_path?: string;
  total_duration?: number;
  total_segments?: number;
  is_public: boolean;
  book_type?: string; // "txt" | "epub"
  epub_structure?: string; // JSON for EPUB metadata
  processing_status?: string; // "ready" | "processing" | "failed"
  processing_error?: string;
  created_at: string;
}

export interface BookListResponse {
  books: Book[];
  total: number;
}

export interface ChapterMeta {
  id: string;
  duration: number;
}

export interface BookManifest {
  chapters: ChapterMeta[];
  totalDuration: number;
}

// 获取书籍列表
export async function getBooks(): Promise<BookListResponse> {
  return request('/books');
}

// 上传书籍
export async function uploadBook(formData: FormData): Promise<Book> {
  return request('/books', {
    method: 'POST',
    body: formData,
  });
}

// 从文本创建有声书 (TTS 转换)
export async function uploadTxtBook(formData: FormData): Promise<Book> {
  return request('/books/from-text', {
    method: 'POST',
    body: formData,
  });
}

// 获取书籍详情
export async function getBook(bookId: string): Promise<Book> {
  return request(`/books/${bookId}`);
}

// 获取书籍章节清单
export async function getBookManifest(bookId: string): Promise<BookManifest> {
  return request(`/books/${bookId}/manifest`);
}

// 获取章节文本
export async function getChapterText(bookId: string, chapterId: string): Promise<string> {
  const response = await fetch(`${API_BASE}/books/${bookId}/chapters/${chapterId}/text`, {
    headers: authStore.getAuthHeader(),
  });
  if (!response.ok) throw new Error('获取章节文本失败');
  return response.text();
}

// 获取章节对齐数据
export async function getChapterAlignment(bookId: string, chapterId: string): Promise<any> {
  return request(`/books/${bookId}/chapters/${chapterId}/alignment`);
}

// 删除书籍
export async function deleteBook(bookId: string): Promise<{ message: string }> {
  return request(`/books/${bookId}`, {
    method: 'DELETE',
  });
}

// 分享书籍
export async function shareBook(
  bookId: string, 
  email?: string
): Promise<{ message: string }> {
  const url = email 
    ? `/books/${bookId}/share?shared_to_email=${encodeURIComponent(email)}`
    : `/books/${bookId}/share`;
  return request(url, {
    method: 'POST',
  });
}

// 获取书籍分享状态
export async function getBookShares(
  bookId: string
): Promise<{
  is_public: boolean;
  shared_users: Array<{
    email: string;
    nickname: string;
    shared_at: string | null;
  }>;
  total_shares: number;
}> {
  return request(`/books/${bookId}/shares`, {
    method: 'GET',
  });
}

// 取消所有分享
export async function unshareBook(
  bookId: string
): Promise<{ message: string; deleted_shares: number }> {
  return request(`/books/${bookId}/shares`, {
    method: 'DELETE',
  });
}

// 保存阅读进度
export async function saveProgress(
  bookId: string,
  data: {
    current_position: number;
    current_segment: number;
    playback_speed: number;
  }
): Promise<any> {
  return request(`/books/${bookId}/progress`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

// 获取阅读进度
export async function getProgress(bookId: string): Promise<any> {
  return request(`/books/${bookId}/progress`);
}
