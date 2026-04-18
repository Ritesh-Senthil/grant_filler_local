import { describe, expect, it } from "vitest";
import { formatLabelDisplay, formatQuestionLabels } from "./questionLabels";

describe("formatQuestionLabels", () => {
  it("numbers by list position", () => {
    expect(formatQuestionLabels(["A", "B", "C"])).toEqual(["1", "2", "3"]);
  });

  it("matches length of input", () => {
    expect(formatQuestionLabels([])).toEqual([]);
  });
});

describe("formatLabelDisplay", () => {
  it("adds a period for numeric mains", () => {
    expect(formatLabelDisplay("1")).toBe("1.");
    expect(formatLabelDisplay("12")).toBe("12.");
  });

  it("passes through non-numeric labels unchanged", () => {
    expect(formatLabelDisplay("1a")).toBe("1a");
  });
});
