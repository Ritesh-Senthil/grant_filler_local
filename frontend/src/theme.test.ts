import { describe, expect, it, beforeEach, afterEach, beforeAll, afterAll } from "vitest";
import {
  THEME_STORAGE_KEY,
  getDocumentTheme,
  initThemeFromStorage,
  parseStoredThemeValue,
  readStoredTheme,
  toggleTheme,
  writeStoredTheme,
} from "./theme";

describe("parseStoredThemeValue", () => {
  it("accepts light and dark", () => {
    expect(parseStoredThemeValue("light")).toBe("light");
    expect(parseStoredThemeValue("dark")).toBe("dark");
  });

  it("rejects null, empty, and garbage", () => {
    expect(parseStoredThemeValue(null)).toBeNull();
    expect(parseStoredThemeValue("")).toBeNull();
    expect(parseStoredThemeValue("system")).toBeNull();
    expect(parseStoredThemeValue("DARK")).toBeNull();
  });
});

/** Vitest's jsdom + Node can expose a partial localStorage; use a full in-memory Storage. */
function createMemoryStorage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() {
      return data.size;
    },
    clear() {
      data.clear();
    },
    getItem(key: string) {
      return data.has(key) ? data.get(key)! : null;
    },
    key(index: number) {
      return [...data.keys()][index] ?? null;
    },
    removeItem(key: string) {
      data.delete(key);
    },
    setItem(key: string, value: string) {
      data.set(key, String(value));
    },
  };
}

describe("theme persistence + DOM", () => {
  let previousStorage: Storage;

  beforeAll(() => {
    previousStorage = globalThis.localStorage;
    globalThis.localStorage = createMemoryStorage();
  });

  afterAll(() => {
    globalThis.localStorage = previousStorage;
  });

  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  afterEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  it("writeStoredTheme + readStoredTheme round-trip", () => {
    expect(readStoredTheme()).toBeNull();
    writeStoredTheme("dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(readStoredTheme()).toBe("dark");
  });

  it("initThemeFromStorage applies dark from storage", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "dark");
    initThemeFromStorage();
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(getDocumentTheme()).toBe("dark");
  });

  it("initThemeFromStorage clears dark when storage is light", () => {
    document.documentElement.classList.add("dark");
    localStorage.setItem(THEME_STORAGE_KEY, "light");
    initThemeFromStorage();
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("initThemeFromStorage defaults to light when missing", () => {
    document.documentElement.classList.add("dark");
    localStorage.removeItem(THEME_STORAGE_KEY);
    initThemeFromStorage();
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("toggleTheme flips preference and storage", () => {
    initThemeFromStorage();
    expect(getDocumentTheme()).toBe("light");
    const next = toggleTheme();
    expect(next).toBe("dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(toggleTheme()).toBe("light");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });
});
