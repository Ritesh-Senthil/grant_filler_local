import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type GrantSummary } from "../api";

export function DashboardPage() {
  const [grants, setGrants] = useState<GrantSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => {
    api
      .listGrants()
      .then(setGrants)
      .catch((e: Error) => setError(e.message));
  };

  useEffect(() => {
    load();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.createGrant({
        name: name.trim(),
        source_type: "pdf",
      });
      setName("");
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Grants</h1>
        <p className="text-slate-600 dark:text-slate-400 mt-1 max-w-2xl">
          Start with a name. On the next screen you&apos;ll add the application (file or web page) and
          get draft answers using your organization profile.
        </p>
      </div>

      <form onSubmit={create} className="flex flex-wrap gap-3 items-end">
        <div className="flex-1 min-w-[220px] max-w-md">
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
            Grant name
          </label>
          <input
            className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 text-slate-900 dark:text-white"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Spring 2026 community grant"
          />
        </div>
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4 py-2 text-sm font-medium"
        >
          Create
        </button>
      </form>

      {error && (
        <div className="rounded-lg bg-red-50 dark:bg-red-950/50 text-red-800 dark:text-red-200 px-4 py-2 text-sm">
          {error}
        </div>
      )}

      {grants === null ? (
        <p className="text-slate-500">Loading…</p>
      ) : grants.length === 0 ? (
        <p className="text-slate-500">No grants yet. Create one above.</p>
      ) : (
        <ul className="divide-y divide-slate-200 dark:divide-slate-700 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden bg-white dark:bg-slate-900/50">
          {grants.map((g) => (
            <li key={g.id}>
              <Link
                to={`/grants/${g.id}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/80"
              >
                <span className="font-medium text-slate-900 dark:text-white">{g.name}</span>
                <span className="text-xs uppercase tracking-wide text-slate-500">{g.status}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
