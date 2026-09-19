import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiBaseUrl = process.env.API_BASE_URL || env.API_BASE_URL || '';

  return {
    plugins: [react()],
    define: {
      'import.meta.env.API_BASE_URL': JSON.stringify(apiBaseUrl),
    },
    build: {
      outDir: 'dist',
    },
  };
});
