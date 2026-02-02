import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		// 代理 API 请求到后端
		proxy: {
			'/api': {
				target: 'http://localhost:8001',
				changeOrigin: true,
			}
		}
	}
});
