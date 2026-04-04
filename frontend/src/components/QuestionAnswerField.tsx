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

export function QuestionAnswerField({
  q,
  a,
  onSave,
  onUserEdit,
}: {
  q: Question;
  a: Answer | undefined;
  onSave: (value: unknown) => void | Promise<void>;
  /** Fires when the user changes input (before save on blur). */
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
              void onSave("Yes");
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
              void onSave("No");
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
              void onSave("");
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
                void onSave(opt);
              }}
            />
            {opt}
          </label>
        ))}
      </div>
    );
  }

  if (t === "multi_choice" && q.options?.length) {
    return <MultiChoiceField q={q} a={a} onSave={onSave} onUserEdit={onUserEdit} />;
  }

  if (t === "number") {
    return <NumberField a={a} onSave={onSave} onUserEdit={onUserEdit} />;
  }

  if (t === "date") {
    return <DateField a={a} onSave={onSave} onUserEdit={onUserEdit} />;
  }

  return (
    <TextLikeField q={q} a={a} onSave={onSave} singleLine={t === "text"} onUserEdit={onUserEdit} />
  );
}

function MultiChoiceField({
  q,
  a,
  onSave,
  onUserEdit,
}: {
  q: Question;
  a: Answer | undefined;
  onSave: (value: unknown) => void | Promise<void>;
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
    void onSave(next);
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
  onSave,
  onUserEdit,
}: {
  a: Answer | undefined;
  onSave: (value: unknown) => void | Promise<void>;
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

  return (
    <input
      type="text"
      inputMode="decimal"
      className={baseField}
      value={local}
      onChange={(e) => {
        onUserEdit?.();
        setLocal(e.target.value);
      }}
      onBlur={() => void onSave(local)}
    />
  );
}

function DateField({
  a,
  onSave,
  onUserEdit,
}: {
  a: Answer | undefined;
  onSave: (value: unknown) => void | Promise<void>;
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
        setLocal(e.target.value);
      }}
      onBlur={() => void onSave(local)}
    />
  );
}

function TextLikeField({
  q,
  a,
  onSave,
  singleLine,
  onUserEdit,
}: {
  q: Question;
  a: Answer | undefined;
  onSave: (value: unknown) => void | Promise<void>;
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

  if (singleLine) {
    return (
      <div className="space-y-1">
        <input
          type="text"
          className={baseField}
          maxLength={maxLen ?? undefined}
          value={local}
          onChange={(e) => {
            onUserEdit?.();
            setLocal(e.target.value);
          }}
          onBlur={() => void onSave(local)}
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
        onChange={(e) => {
          onUserEdit?.();
          setLocal(e.target.value);
        }}
        onBlur={() => void onSave(local)}
      />
      {hint}
    </div>
  );
}
