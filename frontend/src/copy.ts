/** User-facing labels — keep jargon out of the main UI. */

export function grantStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: "Getting started",
    ready: "In progress",
  };
  return labels[status] ?? status.replace(/_/g, " ");
}

export function questionTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    textarea: "Long answer",
    text: "Short answer",
    single_choice: "Pick one",
    multi_choice: "Pick any that apply",
    yes_no: "Yes / No",
    number: "Number",
    date: "Date",
  };
  return labels[type] ?? type.replace(/_/g, " ");
}
