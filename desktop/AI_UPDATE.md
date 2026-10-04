# Update an existing GrantFiller Windows installation

Your original Setup Windows.cmd must have completed on this laptop. Use the same Windows login account as that installation. You do not need to reinstall GrantFiller.

1. Extract the entire update ZIP. Do not run it from inside the ZIP.
2. Finish any running grant job.
3. Double-click **Upgrade AI Windows.cmd**. Keep the laptop plugged in, online, and the window open.
4. Wait for **AI UPDATE COMPLETE: qwen2.5:7b-instruct**. The new model is about a 4.7 GB download; download time depends on the office connection.
5. Test a real grant and time the drafting. On an i7-11370H / Intel Iris Xe, 7B may take noticeably longer than 3B. The 32 GB RAM provides memory headroom, but does not guarantee faster AI.

The update keeps grants, organization facts, uploads, exports, backups and the existing desktop launch icon. It tests actual local AI before switching models and restarts the background app automatically. Repair is updated to preserve the selected model. The old 3B model stays available.

## Choosing a model later

Open **GrantFiller AI Options** on the desktop:

- **1 — Faster (3B):** the original model.
- **2 — More detail (7B):** the larger model; compare its answers and wait time on a real grant before choosing it for everyday use.

Let any grant job finish before switching. Both choices run locally; the regular GrantFiller icon works as before. After the update, reopen or refresh an already-open GrantFiller browser tab. Once updated, this download folder can be moved or deleted; the installed selector remains available.

## If the update fails

Read the error in the window. A failed model download or AI test leaves the current model selected. If activation fails, the updater restores the previous model setting. Saved data remains in `%LOCALAPPDATA%\GrantFiller\data`. Use the existing Repair GrantFiller shortcut if the app will not start. If it still fails, share `%LOCALAPPDATA%\GrantFiller\logs` with Ritesh.

## Verification

Windows and Mac automated checks passed model switching, returning to 3B, preserving saved answers, and rejecting an invalid AI result without changing the current app. The Windows check creates the real AI Options shortcut and checks PowerShell syntax. These automated model checks use a simulated AI service. The updater tests actual Ollama on this laptop before activating 7B. Test run: https://github.com/Ritesh-Senthil/grant_filler_local/actions/runs/37225036889 .

Official 7B model and download size: https://ollama.com/library/qwen2.5:7b-instruct .
