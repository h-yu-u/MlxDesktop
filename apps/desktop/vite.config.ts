import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: { host: '127.0.0.1', port: 1420, strictPort: true },
  clearScreen: false,
  test: { environment: 'jsdom', include: ['src/**/*.spec.ts'] },
})
