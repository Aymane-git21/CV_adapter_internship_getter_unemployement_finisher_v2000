import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    root: '.',
    build: {
        outDir: 'static/dist',
        emptyOutDir: true,
        assetsDir: 'assets',
        rollupOptions: {
            input: 'index.html',
        }
    },
    server: {
        proxy: {
            '/api': {
                target: 'http://127.0.0.1:5000',
                changeOrigin: true,
                secure: false,
            },
            '/download': {
                target: 'http://127.0.0.1:5000',
                changeOrigin: true,
            },
            '/view': {
                target: 'http://127.0.0.1:5000',
                changeOrigin: true,
            }
        }
    }
})
