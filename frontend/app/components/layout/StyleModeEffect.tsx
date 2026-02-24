import { useEffect } from "react";
import { useStyleModeStore } from "~/stores/styleModeStore";
import { useThemeStore } from "~/stores/themeStore";

export function StyleModeEffect() {
  const { styleMode } = useStyleModeStore();
  const { setTheme } = useThemeStore();

  useEffect(() => {
    if (styleMode === "realistic") {
      setTheme("cinematic");
    } else {
      setTheme("doodle");
    }
  }, [styleMode, setTheme]);

  return null;
}
