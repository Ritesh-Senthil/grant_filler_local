import { useEffect, useState } from "react";
import type { Answer, Question } from "../api";

const baseField =
  "w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100";

function toYesNo(v: unknown): "" | "Yes" | "No" {
  if (v === null || v === undefined || v === "") return "";
  const s = String(v).trim();
  if (s.toLowerCase() === "yes" || s === "Yes") return "Yes";
  if (s.toLowerCase() === "no" || s === "No") return "No";
  return "";
}

/**
 * Controlled answer editor: updates the parent draft via `onValueChange` only
 * (no API calls — the grant page saves explicitly).
 */
export function QuestionAnswerField({
  q,
  a,
  onValueChange,
  onUserEdit,
}: {
  q: Question;
  a: Answer | undefined;
  onValueChange: (value: unknown) => void;
  onUserEdit?: () => void;
}) {
  const t = q.type;

  const touch = () => onUserEdit?.();

  if (t === "yes_no") {
    const sel = toYesNo(a?.answer_value);
    return (
      <div className="flex flex-wrap gap-6">
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="radio"
            name={`yn-${q.question_id}`}
            checked={sel === "Yes"}
            onChange={() => {
              touch();
              onValueChange("Yes");
            }}
          />
          Yes
        </label>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="radio"
            name={`yn-${q.question_id}`}
            checked={sel === "No"}
            onChange={() => {
              touch();
              onValueChange("No");
            }}
          />
          No
        </label>
        <label className="flex items-center gap-2 text-sm cursor-pointer text-slate-500">
          <input
            type="radio"
            name={`yn-${q.question_id}`}
            checked={sel === ""}
            onChange={() => {
              touch();
              onValueChange("");
            }}
          />
          Clear
        </label>
      </div>
    );
  }

  if (t === "single_choice" && q.options?.length) {
    const raw = a?.answer_value;
    const sel = typeof raw === "string" ? raw : "";
    return (
      <div className="space-y-2">
        {q.options.map((opt) => (
          <label key={opt} className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="radio"
              name={`sc-${q.question_id}`}
              value={opt}
              checked={sel === opt}
              onChange={() => {
                touch();
                onValueChange(opt);
              }}
            />
            {opt}
          </label>
        ))}
      </div>
    );
  }

  if (t === "multi_choice" && q.options?.length) {
    return <MultiChoiceField q={q} a={a} onValueChange={onValueChange} onUserEdit={onUserEdit} />;
  }

  if (t === "number") {
    return <NumberField a={a} onValueChange={onValueChange} onUserEdit={onUserEdit} />;
  }

  if (t === "date") {
    return <DateField a={a} onValueChange={onValueChange} onUserEdit={onUserEdit} />;
  }

  return (
    <TextLikeField
      q={q}
      a={a}
      onValueChange={onValueChange}
      singleLine={t === "text"}
      onUserEdit={onUserEdit}
    />
  );
}

function MultiChoiceField({
  q,
  a,
  onValueChange,
  onUserEdit,
}: {
  q: Question;
  a: Answer | undefined;
  onValueChange: (value: unknown) => void;
  onUserEdit?: () => void;
}) {
  const raw = a?.answer_value;
  const initial = Array.isArray(raw) ? raw.filter((x): x is string => typeof x === "string") : [];
  const [selected, setSelected] = useState<string[]>(initial);

  useEffect(() => {
    const r = a?.answer_value;
    setSelected(Array.isArray(r) ? r.filter((x): x is string => typeof x === "string") : []);
  }, [a?.answer_value]);

  function toggle(opt: string) {
    onUserEdit?.();
    const next = selected.includes(opt) ? selected.filter((x) => x !== opt) : [...selected, opt];
    setSelected(next);
    onValueChange(next);
  }

  return (
    <div className="space-y-2">
      {q.options!.map((opt) => (
        <label key={opt} className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={selected.includes(opt)} onChange={() => toggle(opt)} />
          {opt}
        </label>
      ))}
    </div>
  );
}

function NumberField({
  a,
  onValueChange,
  onUserEdit,
}: {
  a: Answer | undefined;
  onValueChange: (value: unknown) => void;
  onUserEdit?: () => void;
}) {
  const v = a?.answer_value;
  const [local, setLocal] = useState(() => {
    if (v === null || v === undefined || v === "") return "";
    return String(v);
  });

  useEffect(() => {
    if (v === null || v === undefined || v === "") setLocal("");
    else setLocal(String(v));
  }, [v]);

  function push(s: string) {
    onUserEdit?.();
    setLocal(s);
    const t = s.trim();
    onValueChange(t === "" ? "" : s);
  }

  return (
    <input
      type="text"
      inputMode="decimal"
      className={baseField}
      value={local}
      onChange={(e) => push(e.target.value)}
    />
  );
}

function DateField({
  a,
  onValueChange,
  onUserEdit,
}: {
  a: Answer | undefined;
  onValueChange: (value: unknown) => void;
  onUserEdit?: () => void;
}) {
  const v = a?.answer_value;
  const [local, setLocal] = useState(() => (typeof v === "string" ? v : ""));

  useEffect(() => {
    setLocal(typeof v === "string" ? v : "");
  }, [v]);

  return (
    <input
      type="date"
      className={baseField}
      value={local}
      onChange={(e) => {
        onUserEdit?.();
        const s = e.target.value;
        setLocal(s);
        onValueChange(s);
      }}
    />
  );
}

function TextLikeField({
  q,
  a,
  onValueChange,
  singleLine,
  onUserEdit,
}: {
  q: Question;
  a: Answer | undefined;
  onValueChange: (value: unknown) => void;
  singleLine: boolean;
  onUserEdit?: () => void;
}) {
  const v = a?.answer_value;
  const [local, setLocal] = useState(() => {
    if (v === null || v === undefined) return "";
    if (Array.isArray(v)) return v.join(", ");
    return String(v);
  });

  useEffect(() => {
    if (v === null || v === undefined) setLocal("");
    else if (Array.isArray(v)) setLocal(v.join(", "));
    else setLocal(String(v));
  }, [v]);

  const maxLen = q.char_limit ?? undefined;
  const hint =
    maxLen != null ? (
      <p className="text-xs text-slate-500">
        {local.length}
        {maxLen ? ` / ${maxLen}` : ""} characters
      </p>
    ) : null;

  function push(s: string) {
    onUserEdit?.();
    setLocal(s);
    onValueChange(s);
  }

  if (singleLine) {
    return (
      <div className="space-y-1">
        <input
          type="text"
          className={baseField}
          maxLength={maxLen ?? undefined}
          value={local}
          onChange={(e) => push(e.target.value)}
        />
        {hint}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <textarea
        className={`${baseField} min-h-[100px]`}
        maxLength={maxLen ?? undefined}
        value={local}
        onChange={(e) => push(e.target.value)}
      />
      {hint}
    </div>
  );
}
