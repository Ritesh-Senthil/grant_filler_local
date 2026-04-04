import { useEffect, useState } from "react";
import { api, type Fact, type Org } from "../api";

export function OrgPage() {
  const [org, setOrg] = useState<Org | null>(null);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setError(null);
    try {
      const [o, f] = await Promise.all([api.getOrg(), api.listFacts()]);
      setOrg(o);
      setFacts(f);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    load();
  }, []);

  async function saveOrg() {
    if (!org) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.putOrg(org);
      setOrg(updated);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

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

  if (!org) {
    return <p className="text-slate-500">Loading…</p>;
  }

  return (
    <div className="space-y-8 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Organization</h1>
        <p className="text-slate-600 dark:text-slate-400 mt-1 max-w-2xl">
          Information about your nonprofit. GrantFiller uses this when writing draft answers—keep it accurate
          and update it anytime.
        </p>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 dark:bg-red-950/50 text-red-800 dark:text-red-200 px-4 py-2 text-sm">
          {error}
        </div>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-medium text-slate-900 dark:text-white">Profile</h2>
        <label className="block text-sm text-slate-700 dark:text-slate-300">Legal name</label>
        <input
          className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2"
          value={org.legal_name}
          onChange={(e) => setOrg({ ...org, legal_name: e.target.value })}
        />
        <label className="block text-sm text-slate-700 dark:text-slate-300">Mission (short)</label>
        <textarea
          className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 min-h-[80px]"
          value={org.mission_short}
          onChange={(e) => setOrg({ ...org, mission_short: e.target.value })}
        />
        <label className="block text-sm text-slate-700 dark:text-slate-300">Mission (long)</label>
        <textarea
          className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 min-h-[120px]"
          value={org.mission_long}
          onChange={(e) => setOrg({ ...org, mission_long: e.target.value })}
        />
        <label className="block text-sm text-slate-700 dark:text-slate-300">Address</label>
        <textarea
          className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2"
          value={org.address}
          onChange={(e) => setOrg({ ...org, address: e.target.value })}
        />
        <button
          type="button"
          onClick={saveOrg}
          disabled={saving}
          className="rounded-lg bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          Save profile
        </button>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-medium text-slate-900 dark:text-white">Facts</h2>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Short facts the AI can reuse when drafting answers. You can add them yourself, or use{" "}
          <strong className="font-medium text-slate-800 dark:text-slate-200">Update organization from these answers</strong>{" "}
          on a grant after you&apos;ve filled in questions.
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
                {f.source && <div className="text-xs text-slate-500 mt-1">Source: {f.source}</div>}
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
