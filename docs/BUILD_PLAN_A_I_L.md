# Build plan: A (Settings) + I (banner/name) + L (developer credits)

This document corrects and replaces earlier informal notes. It matches locked roadmap intent and the clarified product model (org-editable header branding vs read-only developer info).

---

## Product model (authoritative)

### Organization (the customer using the app)

- They **edit in Settings**:
  - **Header display name** — short label next to / integrated with the main site header.
  - **Banner image** — upload as-is; **fit to header** via layout/CSS (e.g. max height, `object-fit`, no in-app crop tool for v1).
  - **Organization profile content** moved off `/org`: legal name, mission, address, extra sections (whatever exists today on the org profile).
- These org fields are **persisted** (API + DB) and **customer-controlled**.

### Developer (app author — you)

- **Not shown in the global header.**
- **Shown only inside Settings** as **read-only** text and hyperlinks (GitHub, LinkedIn, sponsor text/url, display name if desired).
- **Not editable** by anyone in the app UI — values come from **build-time config**, **environment**, or a **seeded/static** bundle (no `PUT` from the browser for this block).

### Org facts

- **`/org` keeps only organization memory / facts** (CRUD for facts).
- No editing of mission, address, legal name, or branding on `/org`; link to **Settings** for those.

---

## A. Settings shell & information architecture

- [ ] Add **`/settings`** route(s) and a **Settings** entry in the main nav.
- [ ] **Remove the theme toggle from the top nav**; theme lives **only** under Settings (Appearance).
- [ ] Move **all preference-like controls** into Settings (roadmap: nothing preference-like outside Settings except facts under `/org`).
- [ ] **`/org`** = **facts only** + short pointer: organization details and header branding are under **Settings**.
- [ ] Settings sections (see order below).
- [ ] **Locale (stub):** control(s) + copy that full locale-driven PDF/UI dates come later; persist choice in `app_preferences.json` when ready to wire **E**.
- [ ] **Enhancement request:** single text field + submit; backend **stub** acceptable until **M** (e.g. log, file append, or placeholder endpoint with TODO).
- [ ] **Abbreviated feature list** in Settings; depth in **K** / `FEATURES.md` later.

---

## I. Company banner & header display name (org-editable)

- [ ] **Backend:** store **banner file key** (and optional metadata) on **Organization** (or equivalent); upload endpoint mirroring grant file uploads; validate type/size.
- [ ] **Backend:** **header display name** string on **Organization** (distinct from legal name if both exist).
- [ ] **Frontend — Settings:** form to edit display name, upload/remove banner, preview.
- [ ] **Frontend — shell:** render **banner + display name** in the **global header** next to the existing “website” header row (GrantFiller + nav), with CSS so the image **fits the header**.

---

## L. Developer info (read-only credits — not org “public profile”)

Roadmap item “public profile” here means: **credits for the developer**, not an end-user-editable profile.

- [ ] **Settings — bottom section:** read-only block: developer **display label** (optional), **GitHub**, **LinkedIn**, **sponsor text**, **sponsor URL** (and any other links you want), as **text + hyperlinks only**.
- [ ] **No** edit fields; **no** placement in the **global header**.
- [ ] **Source of truth:** env vars (e.g. `VITE_DEV_*` / `GRANTFILLER_DEV_*`) or static config shipped with the build — **not** stored as editable org data.

---

## Settings page — recommended section order (top → bottom)

1. **Organization profile** — legal name, mission, address, extra sections (moved from current Org page).
2. **Header branding (I)** — display name + banner (org-editable).
3. **Appearance** — theme (moved from nav).
4. **LLM** — existing config / provider UI.
5. **Locale** — stub + persistence hook.
6. **Features** — short bullets.
7. **Enhancement request** — single field + submit (stub backend).
8. **Developer credits (L)** — read-only links (bottom).

Optional placeholder: **Account** (email / password) disabled or “Coming with auth” until **H**.

---

## Routing & nav

| Route        | Purpose |
|-------------|---------|
| `/settings` | All of the above |
| `/org`      | Org facts only |
| `/`, `/grants/:id` | Unchanged |

Nav: **Grants** | **Your organization** (facts) | **Settings** | (no theme button in nav).

---

## Data & API (directional)

- **Organization:** add fields e.g. `header_display_name`, `banner_file_key` (+ migration).
- **Org `GET/PUT`:** include new fields; banner via `POST` multipart dedicated route if preferred.
- **Developer credits:** **no** customer-write API; optional `GET /api/v1/app/developer-credits` returning JSON from server env for the Settings page, or **frontend-only** constants from Vite env (simpler for static deploys).

---

## Out of scope for this epic

- **H** Real auth / editable account in Settings (stub OK).
- **M** Real email delivery for enhancement submissions.
- **E** Wiring export timestamps to locale (until Settings locale is fully specified).

---

## Suggested implementation order

1. Schema + API for org header name + banner; file upload.
2. `/settings` shell + move org profile from `/org`; trim `/org` to facts.
3. Header UI: banner + org display name.
4. Settings: theme + LLM moved; locale stub + enhancement stub.
5. Settings bottom: read-only developer credits (env-driven).
6. Tests + polish.

---

## Changelog

| Date       | Notes |
|------------|--------|
| 2026-04-18 | Initial corrected plan: org-editable header branding; developer read-only in Settings only; facts-only `/org`. |
