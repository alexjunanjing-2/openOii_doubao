import { create } from "zustand";
import { persist } from "zustand/middleware";

type Theme = "doodle" | "doodle-dark" | "cinematic" | "cinematic-light";

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
        const currentTheme = get().theme;
        let newTheme: Theme;
        if (currentTheme === "doodle") {
          newTheme = "doodle-dark";
        } else if (currentTheme === "doodle-dark") {
          newTheme = "doodle";
        } else if (currentTheme === "cinematic") {
          newTheme = "cinematic-light";
        } else {
          newTheme = "cinematic";
        }
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
        if (state?.theme) {
          document.documentElement.setAttribute("data-theme", state.theme);
        }
      },
    }
  )
);
