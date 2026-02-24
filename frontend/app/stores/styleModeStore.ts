import { create } from "zustand";
import { persist } from "zustand/middleware";

type StyleMode = "cartoon" | "realistic";

interface StyleModeState {
  styleMode: StyleMode;
  toggleStyleMode: () => void;
  setStyleMode: (mode: StyleMode) => void;
}

export const useStyleModeStore = create<StyleModeState>()(
  persist(
    (set, get) => ({
      styleMode: "cartoon",
      toggleStyleMode: () => {
        const newMode = get().styleMode === "cartoon" ? "realistic" : "cartoon";
        document.documentElement.setAttribute("data-style-mode", newMode);
        set({ styleMode: newMode });
      },
      setStyleMode: (mode: StyleMode) => {
        document.documentElement.setAttribute("data-style-mode", mode);
        set({ styleMode: mode });
      },
    }),
    {
      name: "openoii-style-mode",
      onRehydrateStorage: () => (state) => {
        if (state?.styleMode) {
          document.documentElement.setAttribute("data-style-mode", state.styleMode);
        }
      },
    }
  )
);
