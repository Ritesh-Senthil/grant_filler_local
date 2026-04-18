/**
 * Display labels from **list order** (roadmap: numbering follows drag-and-drop order).
 */

/** How to show the label beside a question (plain mains get a trailing period). */
export function formatLabelDisplay(label: string): string {
  if (/^\d+$/.test(label)) return `${label}.`;
  return label;
}

/** One label per question, in order: 1, 2, 3, … */
export function formatQuestionLabels(questionTexts: string[]): string[] {
  return questionTexts.map((_, i) => String(i + 1));
}
