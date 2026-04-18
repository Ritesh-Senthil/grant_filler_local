/**
 * Tailwind dark mode uses the `dark` class on <html> (see tailwind.config).
 * Preference is persisted so full page loads (refresh, external links) keep the theme.
 */

export const THEME_STORAGE_KEY = "grantfiller.theme";

export type ThemePreference = "light" | "dark";

/** Normalize a value from localStorage (or elsewhere). Invalid → null (use default light). */
export function parseStoredThemeValue(raw: string | null): ThemePreference | null {
  if (raw === "dark" || raw === "light") return raw;
  return null;
}

export function readStoredTheme(): ThemePreference | null {
  try {
    return parseStoredThemeValue(localStorage.getItem(THEME_STORAGE_KEY));
  } catch {
    return null;
  }
}

export function writeStoredTheme(theme: ThemePreference): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Quota, private mode, or disabled storage — UI still updates for this session.
  }
}

export function applyThemeToDocument(theme: ThemePreference): void {
  const root = document.documentElement;
  if (theme === "dark") root.classList.add("dark");
  else root.classList.remove("dark");
}

export function getDocumentTheme(): ThemePreference {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

/** Apply saved preference, or default (light). Call once at startup. */
export function initThemeFromStorage(): void {
  const stored = readStoredTheme();
  if (stored) applyThemeToDocument(stored);
  else applyThemeToDocument("light");
}

/**
 * Toggle light ↔ dark and persist. Returns the new preference.
 */
export function toggleTheme(): ThemePreference {
  const next: ThemePreference = getDocumentTheme() === "dark" ? "light" : "dark";
  applyThemeToDocument(next);
  writeStoredTheme(next);
  return next;
}

/** Set light or dark explicitly (e.g. Settings). */
export function setThemePreference(theme: ThemePreference): void {
  applyThemeToDocument(theme);
  writeStoredTheme(theme);
}
