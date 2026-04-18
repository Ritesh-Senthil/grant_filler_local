import { describe, expect, it } from "vitest";
import type { Answer, Question } from "../api";
import { answerSufficientForReview } from "./answerReview";

const q = (type: string): Question => ({
  question_id: "x",
  question_text: "?",
  type,
  options: [],
  required: false,
  char_limit: null,
  sort_order: 0,
});

describe("answerSufficientForReview", () => {
  it("rejects missing, empty, and INSUFFICIENT_INFO strings", () => {
    expect(answerSufficientForReview(q("textarea"), undefined)).toBe(false);
    expect(answerSufficientForReview(q("textarea"), { question_id: "x", answer_value: null } as Answer)).toBe(
      false
    );
    expect(answerSufficientForReview(q("textarea"), mk("   "))).toBe(false);
    expect(answerSufficientForReview(q("textarea"), mk("INSUFFICIENT_INFO"))).toBe(false);
    expect(answerSufficientForReview(q("textarea"), mk("insufficient_info"))).toBe(false);
  });

  it("accepts non-empty text", () => {
    expect(answerSufficientForReview(q("textarea"), mk("Hello"))).toBe(true);
  });

  it("accepts Yes/No selections", () => {
    expect(answerSufficientForReview(q("yes_no"), mk("Yes"))).toBe(true);
    expect(answerSufficientForReview(q("yes_no"), mk(""))).toBe(false);
  });

  it("accepts number including zero", () => {
    expect(answerSufficientForReview(q("number"), mk(0))).toBe(true);
    expect(answerSufficientForReview(q("number"), mk(""))).toBe(false);
  });

  it("requires at least one multi_choice option", () => {
    expect(answerSufficientForReview(q("multi_choice"), mk([]))).toBe(false);
    expect(answerSufficientForReview(q("multi_choice"), mk(["A"]))).toBe(true);
  });
});

function mk(answer_value: unknown): Answer {
  return {
    question_id: "x",
    answer_value,
    reviewed: false,
    needs_manual_input: false,
    evidence_fact_ids: [],
  };
}
