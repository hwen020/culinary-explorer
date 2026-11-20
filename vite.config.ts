import {defineConfig, loadEnv} from 'vite'

export default defineConfig(({mode}) => {
  const env = loadEnv(mode, '.', 'CULINARY_')
  return {server: {proxy: {'/api': env.CULINARY_API_TARGET || 'http://127.0.0.1:8000'}}}
})
