import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
    plugins: [react()],
    server: {
        port: 5175,
        strictPort: true,
        proxy: {
            "/ws": {
                target: "http://localhost:8001",
                changeOrigin: true,
                ws: true,
            },
            "/api": {
                target: "http://localhost:8001",
                changeOrigin: true,
            }
        }
    }
});
