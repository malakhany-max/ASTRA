import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const root = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      { find: /^@astra\/shared$/, replacement: `${root}../packages/shared/src/index.ts` },
      { find: /^@astra\/shared\/styles$/, replacement: `${root}../packages/shared/src/styles.ts` },
      { find: /^@astra\/shared\/mock$/, replacement: `${root}../packages/shared/src/mock/index.ts` },
      { find: /^@contracts$/, replacement: `${root}../packages/contracts/src/index.ts` },
      { find: /^@contracts\//, replacement: `${root}../packages/contracts/src/` },
    ],
  },
  server: { port: 5173, strictPort: true },
  preview: { port: 5173, strictPort: true },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/recharts/') || id.includes('/node_modules/d3-')) return 'charts'
          if (/\/node_modules\/(react|react-dom|scheduler|react-router|react-router-dom|@remix-run\/router)\//.test(id)) return 'framework'
          if (id.includes('/node_modules/lucide-react/')) return 'icons'
        },
      },
    },
  },
})
