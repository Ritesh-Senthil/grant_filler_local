import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { clearActiveJob, readActiveJob, saveActiveJob } from "./activeJob";

describe("active job storage", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it("restores a tracked job for the same grant", () => {
    saveActiveJob("grant-1", { jobId: "job-1", label: "Writing drafts" });

    expect(readActiveJob("grant-1")).toEqual({ jobId: "job-1", label: "Writing drafts" });
    expect(readActiveJob("grant-2")).toBeNull();
  });

  it("does not clear a newer job when an older poll finishes", () => {
    saveActiveJob("grant-1", { jobId: "job-new", label: "Writing drafts" });

    clearActiveJob("grant-1", "job-old");

    expect(readActiveJob("grant-1")).toEqual({ jobId: "job-new", label: "Writing drafts" });
  });

  it("clears the matching completed job", () => {
    saveActiveJob("grant-1", { jobId: "job-1", label: "Finding questions" });

    clearActiveJob("grant-1", "job-1");

    expect(readActiveJob("grant-1")).toBeNull();
  });
});
