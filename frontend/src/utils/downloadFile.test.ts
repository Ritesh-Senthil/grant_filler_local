import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { downloadExportedFile } from "./downloadFile";

describe("downloadExportedFile", () => {
  const origFetch = globalThis.fetch;
  const origCreate = globalThis.URL.createObjectURL;
  const origRevoke = globalThis.URL.revokeObjectURL;

  beforeEach(() => {
    globalThis.fetch = vi.fn();
    globalThis.URL.createObjectURL = vi.fn(() => "blob:mock");
    globalThis.URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    globalThis.fetch = origFetch;
    globalThis.URL.createObjectURL = origCreate;
    globalThis.URL.revokeObjectURL = origRevoke;
  });

  it("fetches with filename query and triggers download", async () => {
    const blob = new Blob(["x"], { type: "application/pdf" });
    vi.mocked(fetch).mockResolvedValue(
      new Response(blob, { status: 200, headers: { "Content-Type": "application/pdf" } })
    );
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    await downloadExportedFile("/api/v1/files/exports/g.pdf", "My_2026-04-17.pdf");

    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/files/exports/g.pdf?filename=" + encodeURIComponent("My_2026-04-17.pdf")
    );
    expect(click).toHaveBeenCalled();
    expect(globalThis.URL.createObjectURL).toHaveBeenCalled();
    expect(globalThis.URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock");
    click.mockRestore();
  });

  it("throws on failed response", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500, statusText: "Err" }));
    await expect(downloadExportedFile("/api/v1/files/x", "a.pdf")).rejects.toThrow();
  });
});
