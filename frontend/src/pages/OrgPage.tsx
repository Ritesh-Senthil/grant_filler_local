import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Fact } from "../api";
import { questionDomId } from "../utils/questionDomId";

function FactProvenance({ f }: { f: Fact }) {
  const structured = Boolean(f.learned_from_grant_id);
  const grantName = (f.learned_from_grant_name || "").trim();
  const linkLabel = grantName || "Grant application";
  const qid = (f.learned_from_question_id || "").trim();
  const to =
    structured && qid
      ? `/grants/${f.learned_from_grant_id}#${questionDomId(qid)}`
      : structured
        ? `/grants/${f.learned_from_grant_id}`
        : "";

  if (structured) {
    return (
      <div className="mt-2 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-700/80 px-3 py-2 text-xs text-slate-600 dark:text-slate-400 space-y-1.5">
        <div className="leading-snug">
          <span className="font-medium text-slate-700 dark:text-slate-300">Learned from </span>
          <Link
            to={to}
            className="text-blue-600 dark:text-blue-400 font-medium underline underline-offset-2 decoration-blue-600/35 dark:decoration-blue-400/35 hover:decoration-blue-600 dark:hover:decoration-blue-400"
          >
            {linkLabel}
          </Link>
          {qid && !f.learned_from_question_preview ? (
            <span className="text-slate-500 dark:text-slate-500">
              {" "}
              (link scrolls to that question on the grant page)
            </span>
          ) : null}
        </div>
        {f.learned_from_question_preview ? (
          <p className="text-slate-600 dark:text-slate-400 leading-snug border-l-2 border-slate-200 dark:border-slate-600 pl-2.5 m-0">
            <span className="text-slate-500 dark:text-slate-500">Form question: </span>
            “{f.learned_from_question_preview}”
          </p>
        ) : null}
      </div>
    );
  }

  const manualSource = (f.source || "").trim();
  if (!manualSource) return null;
  return (
    <p className="text-xs text-slate-500 mt-2 m-0">
      <span className="font-medium text-slate-600 dark:text-slate-400">Source: </span>
      {manualSource}
    </p>
  );
}

export function OrgPage() {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    try {
      const f = await api.listFacts();
      setFacts(f);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const [newKey, setNewKey] = useState("");
  const [newVal, setNewVal] = useState("");
  const [newSrc, setNewSrc] = useState("");

  async function addFact(e: React.FormEvent) {
    e.preventDefault();
    if (!newKey.trim() && !newVal.trim()) return;
    setError(null);
    try {
      await api.createFact({ key: newKey, value: newVal, source: newSrc });
      setNewKey("");
      setNewVal("");
      setNewSrc("");
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function removeFact(id: string) {
    if (!confirm("Delete this fact?")) return;
    await api.deleteFact(id);
    load();
  }

  return (
    <div className="space-y-8 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Organization facts</h1>
        <p className="text-slate-600 dark:text-slate-400 mt-1 max-w-2xl">
          Reusable details GrantFiller can cite when drafting answers. Header branding lives in{" "}
          <Link to="/settings" className="text-blue-600 dark:text-blue-400 font-medium underline underline-offset-2">
            Settings
          </Link>
          .
        </p>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 dark:bg-red-950/50 text-red-800 dark:text-red-200 px-4 py-2 text-sm">
          {error}
        </div>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-medium text-slate-900 dark:text-white">Facts</h2>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Short facts the AI can reuse when drafting answers. Add them here, or run{" "}
          <strong className="font-medium text-slate-800 dark:text-slate-200">Update organization from these answers</strong>{" "}
          on a grant after you fill in answers — we&apos;ll show where each learned fact came from.
        </p>
        <form onSubmit={addFact} className="grid gap-2 sm:grid-cols-3">
          <input
            placeholder="Key"
            className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
          />
          <input
            placeholder="Value"
            className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 sm:col-span-2"
            value={newVal}
            onChange={(e) => setNewVal(e.target.value)}
          />
          <input
            placeholder="Source (optional)"
            className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 sm:col-span-3"
            value={newSrc}
            onChange={(e) => setNewSrc(e.target.value)}
          />
          <button
            type="submit"
            className="rounded-lg border border-slate-300 dark:border-slate-600 px-4 py-2 text-sm w-fit"
          >
            Add fact
          </button>
        </form>

        <ul className="divide-y divide-slate-200 dark:divide-slate-700 rounded-xl border border-slate-200 dark:border-slate-700">
          {facts.map((f) => (
            <li key={f.id} className="px-4 py-3 flex justify-between gap-4">
              <div>
                <div className="font-medium text-slate-900 dark:text-white">{f.key || "(no key)"}</div>
                <div className="text-sm text-slate-600 dark:text-slate-400 whitespace-pre-wrap">{f.value}</div>
                <FactProvenance f={f} />
              </div>
              <button
                type="button"
                onClick={() => removeFact(f.id)}
                className="text-sm text-red-600 dark:text-red-400 shrink-0"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
