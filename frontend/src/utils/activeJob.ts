export type ActiveJob = {
  jobId: string;
  label: string;
};

function storageKey(grantId: string): string {
  return `grantfiller.active-job.${grantId}`;
}

export function readActiveJob(grantId: string): ActiveJob | null {
  try {
    const raw = window.sessionStorage.getItem(storageKey(grantId));
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      !parsed ||
      typeof parsed !== "object" ||
      typeof (parsed as ActiveJob).jobId !== "string" ||
      typeof (parsed as ActiveJob).label !== "string"
    ) {
      return null;
    }
    return parsed as ActiveJob;
  } catch {
    return null;
  }
}

export function saveActiveJob(grantId: string, job: ActiveJob): void {
  try {
    window.sessionStorage.setItem(storageKey(grantId), JSON.stringify(job));
  } catch {
    // Tracking is a UI convenience. The server job still runs without browser storage.
  }
}

export function clearActiveJob(grantId: string, expectedJobId?: string): void {
  try {
    const current = readActiveJob(grantId);
    if (expectedJobId && current?.jobId !== expectedJobId) return;
    window.sessionStorage.removeItem(storageKey(grantId));
  } catch {
    // Nothing to clean up if session storage is unavailable.
  }
}
