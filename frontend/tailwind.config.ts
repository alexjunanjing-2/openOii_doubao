import type { Config } from "tailwindcss";
import daisyui from "daisyui";

export default {
  content: ["./app/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        heading: ["Fredoka", "Comic Neue", "sans-serif"],
        sans: ["Nunito", "Comic Neue", "sans-serif"],
        sketch: ["Caveat", "cursive"],
      },
      boxShadow: {
        'brutal': '4px 4px 0px 0px oklch(var(--bc) / 0.3)',
        'brutal-sm': '2px 2px 0px 0px oklch(var(--bc) / 0.3)',
        'brutal-lg': '6px 6px 0px 0px oklch(var(--bc) / 0.3)',
        'brutal-hover': '6px 6px 0px 0px oklch(var(--bc) / 0.3)',
      },
      borderWidth: {
        '3': '3px',
      },
    },
  },
  plugins: [daisyui],
  daisyui: {
    themes: [
      {
        doodle: {
          "primary": "#FFDE59",          // 明亮黄色
          "primary-content": "#1a1a1a",
          "secondary": "#FF71CE",         // 粉色
          "secondary-content": "#1a1a1a",
          "accent": "#00D9FF",            // 青色
          "accent-content": "#1a1a1a",
          "neutral": "#1a1a1a",
          "neutral-content": "#ffffff",
          "base-100": "#FFFEF0",          // 米白色背景（像纸张）
          "base-200": "#FFF9E0",
          "base-300": "#FFF3C4",
          "base-content": "#1a1a1a",
          "info": "#00D9FF",
          "info-content": "#1a1a1a",
          "success": "#7CFC00",           // 草绿色
          "success-content": "#1a1a1a",
          "warning": "#FF9F1C",           // 橙色
          "warning-content": "#1a1a1a",
          "error": "#FF5757",             // 红色
          "error-content": "#ffffff",
        },
      },
      {
        "doodle-dark": {
          "primary": "#FFDE59",
          "primary-content": "#1a1a1a",
          "secondary": "#FF71CE",
          "secondary-content": "#1a1a1a",
          "accent": "#00D9FF",
          "accent-content": "#1a1a1a",
          "neutral": "#2a2a2a",
          "neutral-content": "#ffffff",
          "base-100": "#1a1a1a",
          "base-200": "#2a2a2a",
          "base-300": "#3a3a3a",
          "base-content": "#ffffff",
          "info": "#00D9FF",
          "info-content": "#1a1a1a",
          "success": "#7CFC00",
          "success-content": "#1a1a1a",
          "warning": "#FF9F1C",
          "warning-content": "#1a1a1a",
          "error": "#FF5757",
          "error-content": "#ffffff",
        },
      },
    ],
    darkTheme: "doodle-dark",
  },
} satisfies Config;
