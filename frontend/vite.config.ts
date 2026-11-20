import type { UserConfig } from 'vite'
import solid from '@solidjs/vite-plugin'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

const config: UserConfig = defineConfig({
  base: '/static/',
  plugins: [solid(), tailwindcss()],
  build: {
    outDir: '../medplatform/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure: proxy => {
          proxy.on('proxyReq', proxyReq => {
            proxyReq.setHeader('origin', 'http://127.0.0.1:8000')
          })
        },
      },
    },
  },
})

export default config
