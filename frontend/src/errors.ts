/**
 * Turn API / network error strings into short, non-technical messages.
 * Falls back to the original text when we don't recognize it.
 */
export function humanizeApiError(raw: unknown): string {
  const message =
    raw instanceof Error
      ? raw.message
      : typeof raw === "string"
        ? raw
        : raw == null
          ? ""
          : String(raw);
  const m = message.trim();
  if (!m) return "Something went wrong. Try again.";


  const low = m.toLowerCase();

  if (low.includes("only https://") || low.includes("https:// urls")) {
    return "Use a secure link (https://) for the application page, or upload a PDF or Word file instead.";
  }
  if (low.includes("web_fetch_allow_http_localhost")) {
    return m; // dev message already explains
  }
  if (low.includes("host_blocked") || low.includes("hostname is not allowed")) {
    return "That address can't be opened from here. Use a public application page or upload a file.";
  }
  if (low.includes("non_public_ip") || low.includes("dns_failed")) {
    return "We couldn't open that web page. Check the link or upload a PDF or Word file.";
  }
  if (low.includes("fetch_failed") || low.includes("ssl") || low.includes("tls")) {
    return "We couldn't load that page securely. Try uploading the form as a PDF or Word file instead.";
  }
  if (low.includes("text_too_short") || low.includes("little or no readable text")) {
    return "We couldn't read enough text from that page. Try a PDF or Word file, or a different page.";
  }
  if (low.includes("playwright install chromium") || low.includes("playwright unavailable")) {
    return "Headless browser isn't installed for URL import. Run: playwright install chromium (from your backend venv). Or upload a PDF.";
  }
  if (low.includes("could not render this page")) {
    return "We couldn't load that page in the browser. Try a PDF or Word export of the form, or a different link.";
  }
  // Generate/draft uses embeddings for retrieval; parse uses chat only. Embedding errors contain
  // "Ollama" but are not "Ollama isn't running" — avoid mislabeling missing nomic-embed-text etc.
  if (
    low.includes("embedding model not found") ||
    (low.includes("ollama embeddings failed") && low.includes("install with"))
  ) {
    return "Draft answers need an embedding model for retrieval. Install the model in OLLAMA_EMBED_MODEL (default nomic-embed-text): run ollama pull nomic-embed-text, then try again.";
  }
  // Wrong chat model tag from Ollama (distinct from embed issues above).
  if (low.includes("ollama:") && low.includes("model not found")) {
    return "The chat model in OLLAMA_MODEL doesn't match an installed tag. Run ollama list and set OLLAMA_MODEL to an exact name from that list.";
  }
  // Server unreachable — match connection symptoms only (never the substring "ollama" alone).
  if (
    low.includes("econnrefused") ||
    low.includes("errno 61") ||
    low.includes("errno 10061") ||
    low.includes("connection refused") ||
    low.includes("all connection attempts failed") ||
    low.includes("failed to establish a new connection") ||
    (low.includes("connect") && low.includes("error") && low.includes("11434"))
  ) {
    return "The AI assistant doesn't seem to be running or reachable. If you use Ollama, start it and check OLLAMA_BASE_URL in your backend .env.";
  }
  if (low.includes("no questions") && low.includes("parse")) {
    return "Find questions from a file or web page first (Step 1).";
  }
  if (low.includes("no questions yet")) {
    return "Find questions from a file or web page first (Step 1).";
  }
  if (low.includes("fill in at least one answer") || low.includes("at least one answer first")) {
    return "Add at least one answer above, then try learning organization facts from this grant again.";
  }
  if (low.includes("timed out") || low.includes("timeout")) {
    return "That took too long. Try a smaller file, or try again when the computer is less busy.";
  }
  if (low.includes("not found") && low.includes("grant")) {
    return "This grant no longer exists. Go back to the grant list.";
  }

  return m;
}
