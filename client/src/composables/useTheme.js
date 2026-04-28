import { ref, watch } from "vue";

const STORAGE_KEY = "inv-mgmt-theme";

const readInitial = () => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch (_) {
    /* localStorage unavailable */
  }
  if (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-color-scheme: dark)").matches
  ) {
    return "dark";
  }
  return "light";
};

const theme = ref(readInitial());

const applyTheme = (value) => {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (value === "dark") root.classList.add("dark");
  else root.classList.remove("dark");
};

applyTheme(theme.value);

watch(theme, (value) => {
  applyTheme(value);
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch (_) {
    /* ignore */
  }
});

export function useTheme() {
  const toggleTheme = () => {
    theme.value = theme.value === "dark" ? "light" : "dark";
  };
  return { theme, toggleTheme };
}
