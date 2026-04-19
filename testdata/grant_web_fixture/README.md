# Sample grant website (URL parse fixture)

## Preview in your browser (no server)

Open `index.html` directly (double-click or **File → Open** in Chrome/Firefox/Safari) to review layout and wording **before** you use it in GrantFiller.

> GrantFiller’s parser fetches URLs over the network; `file://` URLs are not used for parsing.

## Serve locally for GrantFiller (recommended)

1. From the **repository root**:

   ```bash
   python3 scripts/serve_grant_web_fixture.py
   ```

2. In **`backend/.env`** set:

   ```env
   WEB_FETCH_ALLOW_HTTP_LOCALHOST=true
   ```

   Restart the API. (Port **8765** is allowed by default; see `WEB_FETCH_HTTP_LOCAL_PORTS` in `.env.example`.)

3. In GrantFiller, create or open a grant, set **Grant URL** to:

   **`http://127.0.0.1:8765/`**

   Use **Preview URL** or **Find questions** (parse from URL) as usual.

This site is **not** part of the Vite/React app (ports **5173** / **8000**); it runs on **8765** only while the script is running.
