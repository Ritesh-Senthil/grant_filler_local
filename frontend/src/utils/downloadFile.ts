import { humanizeApiError } from "../errors";

/**
 * Fetch an export from `GET /api/v1/files/...` with attachment headers and trigger a file save
 * (avoids opening PDF/Markdown in a new tab).
 */
export async function downloadExportedFile(downloadPath: string, filename: string): Promise<void> {
  const q = `filename=${encodeURIComponent(filename)}`;
  const url = downloadPath.includes("?") ? `${downloadPath}&${q}` : `${downloadPath}?${q}`;
  const res = await fetch(url);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = (await res.json()) as { detail?: string };
      if (typeof j.detail === "string") detail = j.detail;
    } catch {
      /* ignore */
    }
    throw new Error(humanizeApiError(detail));
  }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objectUrl);
}
