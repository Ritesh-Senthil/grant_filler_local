import { describe, expect, it } from "vitest";
import { humanizeApiError } from "./errors";

describe("humanizeApiError", () => {
  it("does not map Ollama embedding errors to server down", () => {
    const msg = humanizeApiError(
      "Ollama embeddings failed (nomic-embed-text): x. Install with: ollama pull nomic-embed-text"
    );
    expect(msg).toContain("embedding");
    expect(msg).toContain("nomic-embed-text");
    expect(msg).not.toMatch(/doesn't seem to be running/i);
  });

  it("maps connection refused to unreachable assistant", () => {
    expect(humanizeApiError("Connection refused to 127.0.0.1:11434")).toMatch(/reachable|running/i);
  });

  it("maps embedding model not found from backend", () => {
    const msg = humanizeApiError(
      "Ollama embedding model not found: nomic-embed-text. Run: ollama pull nomic-embed-text"
    );
    expect(msg).toContain("embedding");
    expect(msg).not.toMatch(/doesn't seem to be running/i);
  });
});
