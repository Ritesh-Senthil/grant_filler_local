# Roadmap

This document captures planned work and locked product decisions. Use it when scoping issues and PRs; update it as items ship.

---

## Locked decisions (reference)

| Topic | Decision |
|-------|------------|
| Defaults / preferences | All defaults live **only under Settings**. Out of the box, nothing preference-like appears outside Settings. **Org facts** stays a **separate** section (not folded into “defaults”). |
| Question numbering | Driven by **list order**. **Drag-and-drop reorder** updates order; numbers **update dynamically**. Multi-part labels (e.g. 3a/3b): use consistent judgment in UI. |
| Mark reviewed | **Block** marking as reviewed when the answer is effectively empty (per question type). When review is allowed and applied, **clear** “needs manual input” / equivalent flags. |
| PDF export | **Single** polished style. Export **date/time** uses **locale**; locale/date display **adjustable in Settings**. No debug tags like `[needs input]` in the PDF. |
| Save | **Per grant**. **Explicit Save button** + **confirmation** before persisting. No reliance on silent/auto-save for that flow. |
| Downloads | Do **not** open exports inline in the browser; prefer **attachment** + Save / Save As behavior. |
| LLM | **Ollama is default**. Model: **`qwen3:8b`**. |
| Auth | **One** hardcoded email identity; **forgot-password reset** supported; **no** session timeout. |
| Branding | **Company banner**: uploaded **image + name** (no legacy “externship” link work). |
| Theme | Fix **theme resetting** when deleting or duplicating a grant (preserve preference across those flows). |
| Profile (Settings) | Name, GitHub, LinkedIn, sponsor — **public-facing** where the app exposes them. |
| Enhancement requests | **Single** text field → **internal email**; **no** analytics for now. |
| Features in Settings | **Short**, **abbreviated** bullets (detail lives in documentation). |

**Open point:** How **forgot password** is delivered (SMTP reset link vs local recovery path). Resolve when implementing auth.

---

## A. Settings shell & information architecture

- [ ] Move anything that acts as “defaults/preferences” into **Settings** only; main app surface stays clean by default.
- [ ] Keep **Org facts** as its own section/navigation, distinct from Settings defaults.
- [ ] Settings areas to plan for: account (email, password), appearance/theme, **locale / date format** (PDF + dated UI), **company banner** (image + name), **public profile**, LLM (Ollama + default model), abbreviated **feature list**, **enhancement request** submit.

---

## B. Questions: numbering & reorder

- [x] Persist **sort order** per grant (`sort_order`; `PUT /api/v1/grants/{id}/questions/reorder`).
- [x] **Drag-and-drop** reorder in the grant UI (@dnd-kit; grip handle; 8px activation).
- [x] Display numbers from current order (**1.**, **2.**, … after each reorder).
- [x] Multi-part: list-order numbering only (see roadmap note — complex 3a/3b heuristics deferred).

---

## C. Answers: reviewed & needs input

- [x] Clearing **needs manual input** when **mark as reviewed** succeeds (PATCH sets `needs_manual_input` false).
- [x] **Block** review when answer is empty/invalid (HTTP 422 + client guard); messaging on checkbox attempt.

---

## D. Save model (per grant)

- [ ] Dirty-state tracking for grant-scoped edits in scope.
- [ ] **Save** control with **confirmation** dialog.
- [ ] Warn on navigate away with unsaved changes (route + beforeunload as appropriate).

---

## E. PDF export

- [x] One polished template; no internal/debug tags in body text (and parallel **DOCX** / Markdown polish in the same export pipeline).
- [x] **Exported at** timestamp using **Settings** locale date preferences (`iso` / `en-US` / `en-GB` in `app_preferences.json`).
- [x] Sensible default download filename; org **header or legal name** in export **body** when set (branding; filename still grant + date). See `docs/BUILD_PLAN_E_F.md`.

---

## F. File downloads

- [x] Backend: `Content-Disposition: attachment` and strong filenames for `exports/*` (RFC 6266 `filename*`).  
- [x] Frontend: `downloadExportedFile` blob + `<a download>` (tests in `downloadFile.test.ts`). See `docs/BUILD_PLAN_E_F.md`.

---

## G. Ollama & model defaults

- [ ] Default inference path: **Ollama** + **`qwen3:8b`** (config/env + docs).
- [ ] Smoke: parse → draft with Ollama path.

---

## H. Authentication

- [ ] Single configured account (hardcoded email / seeded identity).
- [ ] Login; change password; **forgot password** reset (mechanism TBD).
- [ ] Protected API routes when unauthenticated; **no** session timeout by policy.

---

## I. Company banner

- [ ] Upload and store banner **image**.
- [ ] **Company name** (and placement with banner in shell/header as designed).

---

## J. Theme persistence bug

- [x] Identify why theme resets on grant **delete** / **duplicate** (full-page `window.location` navigations + non-persisted `dark` class).
- [x] Persist theme in `localStorage` (`grantfiller.theme`), apply on load (inline + `initThemeFromStorage`), use **React Router `navigate()`** instead of hard navigations for delete/duplicate. Frontend tests in `src/theme.test.ts`.

---

## K. Documentation

- [x] **`FEATURES.md`** (repo root): end-user + contributor overview (features, architecture, costs, dependencies). Settings feature bullets stay **abbreviated**; depth lives in this file.

---

## L. Public profile & sponsor

- [ ] Fields: name, GitHub, LinkedIn, sponsor (public-facing surfaces TBD in UI).
- [ ] Reasonable URL validation where applicable.

---

## M. Enhancement / contact

- [ ] Single text submission path to **internal email** (backend integration as chosen).

---

## Suggested implementation order

1. **J** (theme bug) — small, unblocks trust in UI state.  
2. **B + C** — question order + review rules — core UX.  
3. **D** — per-grant save + confirmation — aligns API usage.  
4. **E + F** — PDF/DOCX polish + downloads (**shipped**; `docs/BUILD_PLAN_E_F.md`).  
5. **A + I + L** — Settings, banner, profile.  
6. **H + M** — auth and internal email (depends on mail story).  
7. **G** — verify Ollama/qwen defaults end-to-end.  
8. **K** — doc pass once behavior stabilizes.

Reorder if a release needs branding or auth earlier.

---

## Changelog

| Date | Notes |
|------|--------|
| 2026-04-12 | Initial roadmap from product comments and follow-up decisions. |
| 2026-04-12 | J shipped: persisted theme + SPA navigation on grant delete/duplicate. |
| 2026-04-15 | B + C shipped: question reorder API + drag UI, list-order labels, reviewed blocks empty + clears needs-input. |
| 2026-04-18 | E + F shipped: PDF/DOCX/MD export polish, **Exported** line from Settings locale, org line in export body; `exports/*` attachment downloads + `downloadFile` client pattern (`docs/BUILD_PLAN_E_F.md`). |
| 2026-04-18 | **K**: comprehensive `FEATURES.md` at repo root (nonprofit + ops guide). |
