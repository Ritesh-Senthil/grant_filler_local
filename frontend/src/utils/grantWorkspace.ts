import type { Answer, GrantDetail, Question } from "../api";

/** URL string shown/edited on the grant page (matches legacy display: grant first, then portal). */
export function urlFromGrant(grant: Pick<GrantDetail, "grant_url" | "portal_url">): string {
  return ((grant.grant_url ?? grant.portal_url) ?? "").trim() || "";
}

/**
 * Loose equality for answer payloads (draft vs server), including multi-select order
 * and numeric string vs number.
 */
export function answerValuesEqual(serverType: string, a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (a == null || b == null) {
    const an = a == null || a === "";
    const bn = b == null || b === "";
    return an && bn;
  }
  if (serverType === "number") {
    const na = typeof a === "number" ? a : typeof a === "string" ? parseFloat(a.trim()) : NaN;
    const nb = typeof b === "number" ? b : typeof b === "string" ? parseFloat(b.trim()) : NaN;
    if (!Number.isNaN(na) && !Number.isNaN(nb)) return na === nb;
  }
  if (typeof a === "number" && typeof b === "string") return String(a) === b.trim();
  if (typeof a === "string" && typeof b === "number") return a.trim() === String(b);
  if (typeof a === "boolean" && typeof b === "string") {
    const bt = b.trim().toLowerCase();
    return (a === true && (bt === "yes" || bt === "true")) || (a === false && (bt === "no" || bt === "false"));
  }
  if (typeof b === "boolean" && typeof a === "string") {
    const at = a.trim().toLowerCase();
    return (b === true && (at === "yes" || at === "true")) || (b === false && (at === "no" || at === "false"));
  }
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    const sa = [...a].map((x) => String(x)).sort();
    const sb = [...b].map((x) => String(x)).sort();
    return sa.every((v, i) => v === sb[i]);
  }
  if (typeof a === "string" && typeof b === "string") {
    if (serverType === "number") {
      const na = parseFloat(a.trim());
      const nb = parseFloat(b.trim());
      if (!Number.isNaN(na) && !Number.isNaN(nb) && a.trim() !== "" && b.trim() !== "") return na === nb;
    }
    return a.trim() === b.trim();
  }
  return false;
}

export function serverAnswerValue(grant: GrantDetail, questionId: string): unknown {
  const a = grant.answers.find((x) => x.question_id === questionId);
  return a?.answer_value;
}

/** True when the visible answer text/value differs from the last loaded server value. */
export function isAnswerDraftDirty(q: Question, grant: GrantDetail, draftValue: unknown | undefined): boolean {
  if (draftValue === undefined) return false;
  const serverVal = serverAnswerValue(grant, q.question_id);
  return !answerValuesEqual(q.type, draftValue, serverVal);
}

export function isGrantWorkspaceDirty(
  grant: GrantDetail,
  nameDraft: string,
  urlDraft: string,
  answerDrafts: Record<string, unknown>
): boolean {
  if (nameDraft.trim() !== (grant.name || "").trim()) return true;
  if (urlDraft.trim() !== urlFromGrant(grant).trim()) return true;
  for (const q of grant.questions) {
    const d = answerDrafts[q.question_id];
    if (d === undefined) continue;
    if (isAnswerDraftDirty(q, grant, d)) return true;
  }
  return false;
}

export function mergeAnswerForDisplay(
  grant: GrantDetail,
  questionId: string,
  draft: unknown | undefined
): Answer | undefined {
  const server = grant.answers.find((a) => a.question_id === questionId);
  const hasDraft = draft !== undefined;
  if (!server && !hasDraft) return undefined;
  if (!server && hasDraft) {
    return {
      question_id: questionId,
      answer_value: draft,
      reviewed: false,
      needs_manual_input: false,
      evidence_fact_ids: [],
    };
  }
  return {
    ...server!,
    answer_value: hasDraft ? draft : server!.answer_value,
  };
}
