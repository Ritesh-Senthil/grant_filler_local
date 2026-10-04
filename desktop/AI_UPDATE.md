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

## Compare 3B and 7B with the same test PDF

The repository already includes [a clean, one-page, 10-question sample grant](https://raw.githubusercontent.com/Ritesh-Senthil/grant_filler_local/main/testdata/grant_pdfs/01_test_grant_clean_linear.pdf). Download it; no real applicant data is included in the PDF.

1. Keep the same organization facts throughout both runs.
2. Choose 3B in GrantFiller AI Options. Create a grant named `Test - 3B`, upload the sample, find questions, and draft answers. Note extraction and drafting time separately, then export the result.
3. Choose 7B. Create `Test - 7B`, upload the same PDF, and repeat.
4. Compare whether all 10 questions were found, answers use your saved facts, constraints are followed, and missing dates or budget amounts are flagged for manual input rather than invented. Certification still needs a person's review.
5. Prefer the model that produces useful drafts at an acceptable wait time on this laptop. The short installation AI test does not measure a whole grant's performance.

## If the update fails

Read the error in the window. A failed model download or AI test leaves the current model selected. If activation fails, the updater restores the previous model setting. Saved data remains in `%LOCALAPPDATA%\GrantFiller\data`. Use the existing Repair GrantFiller shortcut if the app will not start. If it still fails, share `%LOCALAPPDATA%\GrantFiller\logs` with Ritesh.

## Verification

Windows and Mac automated checks passed model switching, returning to 3B, preserving saved answers, and rejecting an invalid AI result without changing the current app. The Windows check creates the real AI Options shortcut and checks PowerShell syntax. These automated model checks use a simulated AI service. The updater tests actual Ollama on this laptop before activating 7B. Test run: https://github.com/Ritesh-Senthil/grant_filler_local/actions/runs/37225036889 .

Official 7B model and download size: https://ollama.com/library/qwen2.5:7b-instruct .
