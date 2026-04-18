import { describe, expect, it } from "vitest";
import type { GrantDetail, Question } from "../api";
import {
  answerValuesEqual,
  isGrantWorkspaceDirty,
  urlFromGrant,
} from "./grantWorkspace";

function minimalGrant(
  overrides: Partial<GrantDetail> & Pick<GrantDetail, "id" | "name">
): GrantDetail {
  return {
    status: "active",
    source_type: "pdf",
    created_at: "",
    updated_at: "",
    grant_url: null,
    portal_url: null,
    source_file_key: null,
    file_name: null,
    export_file_key: null,
    source_chunk_count: 0,
    questions: [],
    answers: [],
    ...overrides,
  };
}

describe("urlFromGrant", () => {
  it("prefers grant_url over portal_url", () => {
    expect(urlFromGrant({ grant_url: "https://a.test", portal_url: "https://b.test" })).toBe("https://a.test");
  });
  it("falls back to portal_url", () => {
    expect(urlFromGrant({ grant_url: null, portal_url: " https://x.test " })).toBe("https://x.test");
  });
});

describe("answerValuesEqual", () => {
  it("treats multi_choice order as irrelevant", () => {
    expect(answerValuesEqual("multi_choice", ["b", "a"], ["a", "b"])).toBe(true);
  });
  it("normalizes number strings", () => {
    expect(answerValuesEqual("number", "3", 3)).toBe(true);
    expect(answerValuesEqual("number", "3.0", 3)).toBe(true);
  });
});

describe("isGrantWorkspaceDirty", () => {
  const q = (id: string, type: string): Question => ({
    question_id: id,
    question_text: "?",
    type,
    options: [],
    required: false,
    char_limit: null,
    sort_order: 0,
  });

  it("detects name change", () => {
    const g = minimalGrant({
      id: "1",
      name: "A",
      questions: [],
    });
    expect(isGrantWorkspaceDirty(g, "B", "", {})).toBe(true);
    expect(isGrantWorkspaceDirty(g, "A ", "", {})).toBe(false);
  });

  it("detects url change", () => {
    const g = minimalGrant({
      id: "1",
      name: "A",
      grant_url: "https://old.test",
      questions: [],
    });
    expect(isGrantWorkspaceDirty(g, "A", "https://new.test", {})).toBe(true);
    expect(isGrantWorkspaceDirty(g, "A", "https://old.test", {})).toBe(false);
  });

  it("detects answer draft drift", () => {
    const g = minimalGrant({
      id: "1",
      name: "G",
      questions: [q("q1", "textarea")],
      answers: [
        {
          question_id: "q1",
          answer_value: "hello",
          reviewed: false,
          needs_manual_input: false,
          evidence_fact_ids: [],
        },
      ],
    });
    expect(isGrantWorkspaceDirty(g, "G", "", {})).toBe(false);
    expect(isGrantWorkspaceDirty(g, "G", "", { q1: "hello" })).toBe(false);
    expect(isGrantWorkspaceDirty(g, "G", "", { q1: "bye" })).toBe(true);
  });
});
