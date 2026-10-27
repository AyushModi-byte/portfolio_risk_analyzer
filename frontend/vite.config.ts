import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Plotly is large; keep it out of the main bundle so the upload screen loads fast.
        manualChunks: (id) => (id.includes('plotly') ? 'plotly' : undefined),
      },
    },
    chunkSizeWarningLimit: 1500,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    restoreMocks: true,
  },
});
