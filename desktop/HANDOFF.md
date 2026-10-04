# GrantFiller: on-site installation

This kit starts with a fresh database. It includes the built interface and application code. Python, Ollama, AI models and the website-import browser are installed on the recipient laptop during setup. Internet is needed for installation and importing websites; drafting from uploaded files runs locally.

## Before starting

- Extract the entire ZIP. Do not run Setup from inside the ZIP.
- Use the recipient's normal login account; that account will own the app and its data.
- Keep the laptop plugged in and connected to reliable internet during setup.
- Current Ollama requires Windows 10 22H2 or newer, or macOS 14 or newer. Check the OS first.
- Allow at least 12 GB of free space. A laptop with 16 GB RAM is preferable; an 8 GB laptop needs a real drafting test before you commit to its performance.
- The chat and embedding models total approximately 2.2 GB of downloads. Ollama and other components need additional downloads.

## Windows

1. Open the extracted folder, then open `desktop`.
2. Double-click `Setup Windows.cmd`. It uses Windows' package manager to install Python and Ollama if missing. Approve official installation prompts. If Windows has no package manager, it opens the official download page; finish installing and rerun Setup.
3. Leave the setup window open while it installs dependencies, Chromium, and both AI models. It tests actual local AI before reporting `SETUP COMPLETE`.
4. Use the new `GrantFiller` desktop shortcut. `Repair GrantFiller` reruns setup while preserving saved work.

## Mac

1. Install Python 3.12 or newer from https://www.python.org/downloads/macos/ and Ollama from https://ollama.com/download/mac if they are missing.
2. Open the extracted folder, open `desktop`, and double-click `Setup Mac.command`. If macOS blocks the downloaded script, open Terminal, type `zsh `, drag `Setup Mac.command` into Terminal, then press Return.
3. Leave the setup window open until `SETUP COMPLETE`. It creates the `GrantFiller.app` desktop icon and a `Repair GrantFiller.command` shortcut.

## Do these checks before leaving

1. Add the nonprofit's real organization facts; the installation is intentionally empty.
2. Upload `Installation test.pdf` from this kit. Click Find questions, then draft answers. Check that AI produced useful answers using the facts you entered.
3. Export a PDF and a Word document. Open both saved files.
4. Close the browser and reopen the GrantFiller desktop icon. Confirm the saved grant is still there.
5. Restart the laptop, log in, and open the icon again. This checks login startup on the actual machine.
6. Turn Wi-Fi off briefly and draft from an uploaded file. Reenable Wi-Fi afterwards.
7. Repeat with one real grant they plan to use.

If drafting is slow on their hardware, tell them the measured wait. Do not promise instant AI. Leave time to finish these checks, not just finish downloading.

## Normal use

Click GrantFiller. It opens in the normal browser, and the supporting processes run invisibly. Closing the browser does not stop an AI job. The backend restarts if it exits. Services start on login, and clicking the icon starts them if needed. A laptop cannot work while shut down or asleep; do not let it sleep during drafting. After an interrupted job, open the grant and run the action again.

## Data and troubleshooting

- Windows installation: `%LOCALAPPDATA%\GrantFiller`
- Mac installation: `~/Library/Application Support/GrantFiller`
- `data` contains the database, organization facts, uploads, preferences and exports.
- `logs` contains startup, backend and Ollama logs. Share these with Ritesh if Repair does not fix the problem.
- `backups` contains up to seven snapshots, created on the first backend startup of a day. These are local recovery copies, not protection against laptop loss.
- Setup can be rerun. It preserves the data folder. Once installed, the downloaded kit can be moved or deleted; the app lives in the installation folder above.
- Keep Python and Ollama installed. Their removal breaks the local app.

## Verification scope

The Windows native verification passed on 2026-10-04: dependency installation, installer syntax, desktop/startup shortcut creation, PDF upload, question extraction, drafting, PDF/Word/Markdown exports, backend crash recovery, duplicate launch, restart persistence and startup backup. This Windows automated run uses a simulated AI service; setup tests actual Ollama on the recipient laptop. View the tested run: https://github.com/Ritesh-Senthil/grant_filler_local/actions/runs/37224035445 .

On the development Mac, a fresh dependency installation and real Ollama inference passed, including the full drafting/export workflow. 153 backend tests and 31 interface tests passed. The recipient's model-download time, hardware speed, permissions and login startup still require on-site checking.
