import { create } from "zustand";
import { persist } from "zustand/middleware";

type Theme = "doodle" | "doodle-dark";

interface ThemeState {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: "doodle",
      toggleTheme: () => {
        const newTheme = get().theme === "doodle" ? "doodle-dark" : "doodle";
        document.documentElement.setAttribute("data-theme", newTheme);
        set({ theme: newTheme });
      },
      setTheme: (theme: Theme) => {
        document.documentElement.setAttribute("data-theme", theme);
        set({ theme });
      },
    }),
    {
      name: "openoii-theme",
      onRehydrateStorage: () => (state) => {
        // 恢复主题时应用到 DOM
        if (state?.theme) {
          document.documentElement.setAttribute("data-theme", state.theme);
        }
      },
    }
  )
);
