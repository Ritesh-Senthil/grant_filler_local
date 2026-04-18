import type { Answer, Question } from "../api";

/**
 * True when the user has provided something that can be marked reviewed
 * (aligned with backend `answer_value_is_effectively_empty`).
 */
export function answerSufficientForReview(_question: Question, a: Answer | undefined): boolean {
  if (!a) return false;
  const v = a.answer_value;
  if (v == null) return false;
  if (typeof v === "string") {
    const s = v.trim();
    if (!s || s.toUpperCase() === "INSUFFICIENT_INFO") return false;
    return true;
  }
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === "number" || typeof v === "boolean") return true;
  return false;
}
