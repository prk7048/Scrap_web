import { copyFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const rootDir = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root: resolve(rootDir, "src"),
  build: {
    emptyOutDir: true,
    outDir: resolve(rootDir, "dist"),
    rollupOptions: {
      input: {
        popup: resolve(rootDir, "src/popup.html"),
        background: resolve(rootDir, "src/background.ts"),
      },
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name].[ext]",
      },
    },
  },
  plugins: [
    {
      name: "copy-extension-manifest",
      async writeBundle() {
        await mkdir(resolve(rootDir, "dist"), { recursive: true });
        await copyFile(resolve(rootDir, "manifest.json"), resolve(rootDir, "dist/manifest.json"));
      },
    },
  ],
});
