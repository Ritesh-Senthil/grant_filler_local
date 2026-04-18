/** DOM fragment id for a question; must match GrantPage question cards. */
export function questionDomId(questionId: string): string {
  return `gf-q-${questionId.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}
