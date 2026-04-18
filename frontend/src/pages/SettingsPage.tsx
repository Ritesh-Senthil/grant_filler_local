import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type DeveloperCredits, type Org } from "../api";
import { humanizeApiError } from "../errors";
import { useOrgBranding } from "../orgBranding";
import { getDocumentTheme, setThemePreference, type ThemePreference } from "../theme";

function sectionCard(
  title: string,
  description: string | undefined,
  children: React.ReactNode
): React.ReactElement {
  return (
    <section className="rounded-2xl border border-slate-200/90 dark:border-slate-700 bg-white dark:bg-slate-900/50 px-5 py-4 space-y-4">
      <div>
        <h2 className="text-base font-semibold text-slate-900 dark:text-white">{title}</h2>
        {description ? (
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-relaxed max-w-2xl">{description}</p>
        ) : null}
      </div>
      {children}
    </section>
  );
}

export function SettingsPage() {
  const { refreshOrgBranding } = useOrgBranding();
  const [org, setOrg] = useState<Org | null>(null);
  const [prefs, setPrefs] = useState<{ locale: string } | null>(null);
  const [credits, setCredits] = useState<DeveloperCredits | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingHeader, setSavingHeader] = useState(false);
  const [llmOk, setLlmOk] = useState<boolean | null>(null);
  const [llmProvider, setLlmProvider] = useState<string | null>(null);
  const [llmSource, setLlmSource] = useState<"env" | "user" | null>(null);
  const [switchingLlm, setSwitchingLlm] = useState(false);
  const [theme, setTheme] = useState<ThemePreference>(() => getDocumentTheme());
  const [enhanceText, setEnhanceText] = useState("");
  const [enhanceBusy, setEnhanceBusy] = useState(false);
  const [localeBusy, setLocaleBusy] = useState(false);
  const [bannerBusy, setBannerBusy] = useState(false);

  const load = async () => {
    setError(null);
    try {
      const [o, p, c] = await Promise.all([
        api.getOrg(),
        api.getPreferences(),
        api.getDeveloperCredits(),
      ]);
      setOrg(o);
      refreshOrgBranding(o);
      setPrefs(p);
      setCredits(c);
      const cfg = await api.config();
      setLlmOk(cfg.llm_configured);
      setLlmProvider(cfg.llm_provider);
      setLlmSource(cfg.llm_provider_source);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  async function saveHeaderName() {
    if (!org) return;
    setSavingHeader(true);
    setError(null);
    try {
      const updated = await api.putOrg({ header_display_name: org.header_display_name });
      setOrg(updated);
      refreshOrgBranding(updated);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSavingHeader(false);
    }
  }

  async function applyLlmProvider(p: "ollama" | "gemini") {
    setSwitchingLlm(true);
    setError(null);
    try {
      const c = await api.setLlmProvider({ llm_provider: p });
      setLlmOk(c.llm_configured);
      setLlmProvider(c.llm_provider);
      setLlmSource(c.llm_provider_source);
    } catch (e) {
      setError(humanizeApiError(e));
    } finally {
      setSwitchingLlm(false);
    }
  }

  async function resetLlmToEnv() {
    setSwitchingLlm(true);
    setError(null);
    try {
      const c = await api.clearLlmPreference();
      setLlmOk(c.llm_configured);
      setLlmProvider(c.llm_provider);
      setLlmSource(c.llm_provider_source);
    } catch (e) {
      setError(humanizeApiError(e));
    } finally {
      setSwitchingLlm(false);
    }
  }

  async function onBannerFile(file: File | null) {
    if (!file) return;
    setBannerBusy(true);
    setError(null);
    try {
      const updated = await api.uploadOrgBanner(file);
      setOrg(updated);
      refreshOrgBranding(updated);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBannerBusy(false);
    }
  }

  async function removeBanner() {
    setBannerBusy(true);
    setError(null);
    try {
      const updated = await api.deleteOrgBanner();
      setOrg(updated);
      refreshOrgBranding(updated);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBannerBusy(false);
    }
  }

  async function onLocaleChange(next: string) {
    setLocaleBusy(true);
    setError(null);
    try {
      const p = await api.patchPreferences({ locale: next });
      setPrefs(p);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLocaleBusy(false);
    }
  }

  async function submitEnhancement(e: React.FormEvent) {
    e.preventDefault();
    if (!enhanceText.trim()) return;
    setEnhanceBusy(true);
    setError(null);
    try {
      await api.submitEnhancement(enhanceText.trim());
      setEnhanceText("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setEnhanceBusy(false);
    }
  }

  if (!org || !prefs || !credits) {
    return <p className="text-slate-500">Loading…</p>;
  }

  const bannerPreview = org.banner_file_key ? api.fileUrl(org.banner_file_key) : null;

  return (
    <div className="space-y-8 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Settings</h1>
        <p className="text-slate-600 dark:text-slate-400 mt-1 max-w-2xl">
          Header branding, appearance, and integrations. Everything the AI should know about your nonprofit (legal name,
          mission, programs, address, and so on) lives as{" "}
          <strong className="font-medium text-slate-800 dark:text-slate-200">facts</strong> — edit them under{" "}
          <Link to="/org" className="text-blue-600 dark:text-blue-400 font-medium underline underline-offset-2">
            Your organization
          </Link>
          .
        </p>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 dark:bg-red-950/50 text-red-800 dark:text-red-200 px-4 py-2 text-sm">
          {error}
        </div>
      )}

      {sectionCard(
        "Header branding",
        "Optional banner and display name appear in the app header. Images are scaled to fit (no in-app crop). Upload replaces the previous image.",
        <>
          <label className="block text-sm text-slate-700 dark:text-slate-300">Header display name</label>
          <input
            className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 text-slate-900 dark:text-white"
            value={org.header_display_name}
            placeholder="e.g. Acme Community Foundation"
            onChange={(e) => setOrg({ ...org, header_display_name: e.target.value })}
          />
          <button
            type="button"
            onClick={() => void saveHeaderName()}
            disabled={savingHeader}
            className="rounded-lg border border-slate-300 dark:border-slate-600 px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            Save display name
          </button>

          <div className="pt-2 space-y-2">
            <span className="text-sm font-medium text-slate-800 dark:text-slate-200">Banner image</span>
            {bannerPreview ? (
              <div className="flex flex-wrap items-end gap-3">
                <img
                  src={bannerPreview}
                  alt=""
                  className="h-14 max-w-[200px] object-cover rounded-md border border-slate-200 dark:border-slate-600"
                />
                <button
                  type="button"
                  disabled={bannerBusy}
                  onClick={() => void removeBanner()}
                  className="text-sm text-red-600 dark:text-red-400 disabled:opacity-50"
                >
                  Remove banner
                </button>
              </div>
            ) : (
              <p className="text-xs text-slate-500 dark:text-slate-400">No banner uploaded.</p>
            )}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif,.jpg,.jpeg,.png,.webp,.gif"
              disabled={bannerBusy}
              onChange={(e) => {
                const f = e.target.files?.[0];
                void onBannerFile(f ?? null);
                e.target.value = "";
              }}
              className="text-sm"
            />
            <p className="text-xs text-slate-500 dark:text-slate-400">
              JPEG, PNG, WebP, or GIF — same size limit as grant uploads.
            </p>
          </div>
        </>
      )}

      {sectionCard(
        "Appearance",
        "Theme applies across the app and is stored in this browser only.",
        <div className="flex flex-wrap gap-2 items-center">
          <button
            type="button"
            onClick={() => {
              setThemePreference("light");
              setTheme("light");
            }}
            className={`rounded-lg border px-3 py-2 text-sm font-medium ${
              theme === "light"
                ? "border-blue-500 bg-blue-50 dark:bg-blue-950/40 text-blue-900 dark:text-blue-100"
                : "border-slate-300 dark:border-slate-600"
            }`}
          >
            Light
          </button>
          <button
            type="button"
            onClick={() => {
              setThemePreference("dark");
              setTheme("dark");
            }}
            className={`rounded-lg border px-3 py-2 text-sm font-medium ${
              theme === "dark"
                ? "border-blue-500 bg-blue-50 dark:bg-blue-950/40 text-blue-900 dark:text-blue-100"
                : "border-slate-300 dark:border-slate-600"
            }`}
          >
            Dark
          </button>
        </div>
      )}

      {sectionCard(
        "LLM / AI backend",
        "Choose local Ollama or Google Gemini. Your choice is saved on this machine (app_preferences.json under your data folder) and overrides LLM_PROVIDER in .env until you reset.",
        <>
          {llmOk === false && (
            <p className="text-sm text-amber-800 dark:text-amber-200 rounded-lg bg-amber-50 dark:bg-amber-950/45 border border-amber-200/80 dark:border-amber-800/50 px-3 py-2">
              AI assistant is not fully configured.{" "}
              {llmProvider === "gemini" ? (
                <>Set GOOGLE_API_KEY in the backend .env for Gemini.</>
              ) : (
                <>Start Ollama locally with the configured model.</>
              )}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={switchingLlm || llmProvider === "ollama"}
              onClick={() => void applyLlmProvider("ollama")}
              className="rounded-lg border border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 px-3 py-2 text-sm font-medium text-slate-900 dark:text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-100 dark:hover:bg-slate-700"
            >
              Ollama (local)
            </button>
            <button
              type="button"
              disabled={switchingLlm || llmProvider === "gemini"}
              onClick={() => void applyLlmProvider("gemini")}
              className="rounded-lg border border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 px-3 py-2 text-sm font-medium text-slate-900 dark:text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-100 dark:hover:bg-slate-700"
            >
              Gemini (cloud)
            </button>
            {llmSource === "user" ? (
              <button
                type="button"
                disabled={switchingLlm}
                onClick={() => void resetLlmToEnv()}
                className="text-sm text-slate-600 dark:text-slate-400 underline underline-offset-2 disabled:opacity-50"
              >
                Use .env default instead
              </button>
            ) : null}
          </div>
          {llmProvider && (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Active: <span className="font-medium text-slate-700 dark:text-slate-300">{llmProvider}</span>
              {llmSource === "user" ? " · saved preference" : " · from environment"}
              {switchingLlm ? " · applying…" : null}
            </p>
          )}
        </>
      )}

      {sectionCard(
        "Locale",
        "Stub for future date and format preferences (exports and in-app dates). Values are saved to app_preferences.json.",
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="locale-select" className="text-sm text-slate-700 dark:text-slate-300">
            Locale
          </label>
          <select
            id="locale-select"
            disabled={localeBusy}
            value={prefs.locale}
            onChange={(e) => void onLocaleChange(e.target.value)}
            className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 text-sm"
          >
            <option value="iso">ISO-style (stub default)</option>
            <option value="en-US">en-US (stub)</option>
            <option value="en-GB">en-GB (stub)</option>
          </select>
        </div>
      )}

      {sectionCard(
        "Features",
        "GrantFiller helps teams draft grant application answers from your materials and org facts.",
        <ul className="list-disc pl-5 text-sm text-slate-600 dark:text-slate-400 space-y-1">
          <li>Parse PDF, DOCX, or web pages into structured questions</li>
          <li>Draft answers with retrieval from your material and organization facts</li>
          <li>Export responses (PDF, Word, Markdown)</li>
          <li>Learn reusable facts from completed applications</li>
        </ul>
      )}

      {sectionCard(
        "Enhancement request",
        "Share feedback; this installation appends requests to a file under the data directory (no email yet).",
        <form onSubmit={(e) => void submitEnhancement(e)} className="space-y-3">
          <textarea
            className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 min-h-[100px] text-slate-900 dark:text-white"
            value={enhanceText}
            onChange={(e) => setEnhanceText(e.target.value)}
            placeholder="What would make GrantFiller more useful for you?"
          />
          <button
            type="submit"
            disabled={enhanceBusy || !enhanceText.trim()}
            className="rounded-lg bg-slate-800 hover:bg-slate-900 dark:bg-slate-100 dark:hover:bg-white text-white dark:text-slate-900 px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            Submit
          </button>
        </form>
      )}

      {sectionCard(
        "Developer",
        "This app’s author links (read-only; configure via server environment).",
        <>
          {(credits.display_name || "").trim() ? (
            <p className="text-sm text-slate-800 dark:text-slate-200">
              <span className="text-slate-500 dark:text-slate-400">Label: </span>
              {credits.display_name}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
            {(credits.github_url || "").trim() ? (
              <a
                href={credits.github_url}
                target="_blank"
                rel="noreferrer"
                className="text-blue-600 dark:text-blue-400 underline underline-offset-2"
              >
                GitHub
              </a>
            ) : null}
            {(credits.linkedin_url || "").trim() ? (
              <a
                href={credits.linkedin_url}
                target="_blank"
                rel="noreferrer"
                className="text-blue-600 dark:text-blue-400 underline underline-offset-2"
              >
                LinkedIn
              </a>
            ) : null}
            {(credits.sponsor_text || "").trim() && (credits.sponsor_url || "").trim() ? (
              <a
                href={credits.sponsor_url}
                target="_blank"
                rel="noreferrer"
                className="text-blue-600 dark:text-blue-400 underline underline-offset-2"
              >
                {credits.sponsor_text}
              </a>
            ) : (credits.sponsor_text || "").trim() ? (
              <span className="text-slate-700 dark:text-slate-300">{credits.sponsor_text}</span>
            ) : null}
          </div>
          {!(credits.display_name || "").trim() &&
          !(credits.github_url || "").trim() &&
          !(credits.linkedin_url || "").trim() &&
          !(credits.sponsor_text || "").trim() &&
          !(credits.sponsor_url || "").trim() ? (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              No developer links configured. Set <code className="text-[11px]">GRANTFILLER_DEV_*</code> in the backend
              environment to show them here.
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
