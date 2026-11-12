import adapter from '@sveltejs/adapter-node';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		// adapter-node 用于 Node.js 环境部署
		adapter: adapter(),
		paths: { base: '/ar', relative: false }
	}
};

export default config;
