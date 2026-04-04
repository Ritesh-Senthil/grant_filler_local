import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { QuestionAnswerField } from "../components/QuestionAnswerField";
import { grantStatusLabel, questionTypeLabel } from "../copy";
import { humanizeApiError } from "../errors";
import { api, type Answer, type GrantDetail, type Question } from "../api";

function answerFor(answers: Answer[], qid: string): Answer | undefined {
  return answers.find((a) => a.question_id === qid);
}

export function GrantPage() {
  const { id } = useParams<{ id: string }>();
  const [grant, setGrant] = useState<GrantDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobMsg, setJobMsg] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [urlDraft, setUrlDraft] = useState("");
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [answersDirty, setAnswersDirty] = useState(false);
  const [saveHint, setSaveHint] = useState<string | null>(null);

  const load = () => {
    if (!id) return;
    api
      .getGrant(id)
      .then(setGrant)
      .catch((e: Error) => setError(humanizeApiError(e)));
  };

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (!answersDirty) return;
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [answersDirty]);

  useEffect(() => {
    load();
  }, [id]);

  useEffect(() => {
    if (grant) setUrlDraft(grant.grant_url ?? "");
  }, [grant?.grant_url, grant?.id]);

  async function pollJob(jobId: string, label: string) {
    let consecutiveErrors = 0;
    for (let i = 0; i < 600; i++) {
      try {
        const j = await api.getJob(jobId);
        consecutiveErrors = 0;
        if (j.status === "completed") {
          if (j.job_kind === "learn_org" && j.result_json && typeof j.result_json === "object") {
            const r = j.result_json as { facts_added?: number; facts_updated?: number };
            const a = r.facts_added ?? 0;
            const u = r.facts_updated ?? 0;
            setJobMsg(
              `Organization profile updated: ${a} new fact${a === 1 ? "" : "s"}, ${u} updated. View them under Your organization.`
            );
            window.setTimeout(() => setJobMsg(null), 10000);
          } else {
            setJobMsg(null);
          }
          load();
          return;
        }
        if (j.status === "failed") {
          setJobMsg(null);
          setError(humanizeApiError(j.error || "Something went wrong."));
          return;
        }
        const pct = Math.round((j.progress ?? 0) * 100);
        setJobMsg(`${label} — about ${pct}%…`);
        await new Promise((r) => setTimeout(r, 800));
      } catch (e) {
        consecutiveErrors += 1;
        setJobMsg(`${label} — connection issue, retrying…`);
        if (consecutiveErrors >= 8) {
          setJobMsg(null);
          setError(humanizeApiError(e));
          return;
        }
        await new Promise((r) => setTimeout(r, 1500));
      }
    }
    setJobMsg(
      "This is taking longer than expected. Check that the AI assistant is running on this computer, then try again."
    );
  }

  async function onUpload(file: File | null) {
    if (!id || !file) return;
    setUploading(true);
    setError(null);
    try {
      await api.uploadFile(id, file);
      load();
    } catch (e) {
      setError(humanizeApiError(e));
    } finally {
      setUploading(false);
    }
  }

  async function parseFromFile() {
    if (!id) return;
    setError(null);
    setJobMsg("Finding questions in your file…");
    try {
      const { job_id } = await api.parse(id, {});
      await pollJob(job_id, "Finding questions");
    } catch (e) {
      setJobMsg(null);
      setError(humanizeApiError(e));
    }
  }

  async function parseFromWeb() {
    if (!id) return;
    const u = urlDraft.trim();
    if (!u) {
      setError("Paste the web address of the application page first.");
      return;
    }
    setError(null);
    setJobMsg("Finding questions on the web page…");
    try {
      await api.putGrant(id, { grant_url: u });
      const { job_id } = await api.parse(id, { use_url: true, url: u });
      await pollJob(job_id, "Finding questions");
    } catch (e) {
      setJobMsg(null);
      setError(humanizeApiError(e));
    }
  }

  async function previewWeb() {
    if (!id) return;
    const u = urlDraft.trim();
    if (!u) {
      setError("Paste a web address first.");
      return;
    }
    setError(null);
    setPreviewLoading(true);
    setPreviewText(null);
    try {
      await api.putGrant(id, { grant_url: u });
      const res = await api.previewUrl(id, { url: u });
      setPreviewText(res.preview);
    } catch (e) {
      setError(humanizeApiError(e));
    } finally {
      setPreviewLoading(false);
    }
  }

  async function learnFromAnswers() {
    if (!id) return;
    setError(null);
    setJobMsg("Updating your organization profile from answers…");
    try {
      const { job_id } = await api.learnOrgFromGrant(id);
      await pollJob(job_id, "Updating organization profile");
    } catch (e) {
      setJobMsg(null);
      setError(humanizeApiError(e));
    }
  }

  async function generate() {
    if (!id) return;
    setError(null);
    setJobMsg("Writing draft answers…");
    try {
      const { job_id } = await api.generate(id);
      await pollJob(job_id, "Writing drafts");
    } catch (e) {
      setJobMsg(null);
      setError(humanizeApiError(e));
    }
  }

  async function exportGrantFormat(format: "qa_pdf" | "markdown" | "docx") {
    if (!id) return;
    setError(null);
    try {
      const { download_path } = await api.exportGrant(id, format);
      window.open(download_path, "_blank");
      load();
    } catch (e) {
      setError(humanizeApiError(e));
    }
  }

  async function patchAnswer(q: Question, value: unknown) {
    if (!id) return;
    setError(null);
    try {
      await api.patchAnswer(id, q.question_id, { answer_value: value });
      setAnswersDirty(false);
      setSaveHint("Saved.");
      window.setTimeout(() => setSaveHint(null), 2500);
      load();
    } catch (e) {
      setError(humanizeApiError(e));
    }
  }

  async function toggleReviewed(q: Question, reviewed: boolean) {
    if (!id) return;
    await api.patchAnswer(id, q.question_id, { reviewed });
    load();
  }

  async function removeGrant() {
    if (!id) return;
    if (!confirm("Delete this grant and its files?")) return;
    await api.deleteGrant(id);
    window.location.href = "/";
  }

  if (!id) return null;
  if (!grant) {
    return <p className="text-slate-500">Loading…</p>;
  }

  const nQuestions = grant.questions.length;

  const saveStatusLine = saveHint ? (
    <span className="text-emerald-700 dark:text-emerald-400 font-medium">{saveHint}</span>
  ) : answersDirty ? (
    <span className="text-amber-800 dark:text-amber-300">Unsaved edits — click outside a field to save.</span>
  ) : nQuestions > 0 ? (
    <span className="text-slate-500 dark:text-slate-400">Answers save when you leave a field.</span>
  ) : (
    <span className="text-slate-500 dark:text-slate-400">Add a file or link below, then find questions.</span>
  );

  const jobPct = jobMsg?.match(/(\d+)%/)?.[1];
  const jobPctNum = jobPct != null ? Math.min(100, Math.max(0, parseInt(jobPct, 10))) : null;

  const actionPanel = (
    <div className="rounded-2xl border border-slate-200/90 bg-white shadow-sm dark:border-slate-700/80 dark:bg-slate-900/80 dark:shadow-none overflow-hidden">
      <div className="border-b border-slate-100 dark:border-slate-800 px-5 py-4 bg-slate-50/80 dark:bg-slate-800/50">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Drafts &amp; export
        </p>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">{saveStatusLine}</p>
      </div>
      <div className="p-5 space-y-4">
        {jobMsg ? (
          <div className="rounded-xl border border-blue-200/90 dark:border-blue-800/50 bg-blue-50/95 dark:bg-blue-950/50 px-3.5 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-blue-700 dark:text-blue-300 mb-2">
              In progress
            </p>
            {jobPctNum != null ? (
              <div className="mb-2">
                <div className="flex justify-between text-xs text-blue-800 dark:text-blue-200 mb-1">
                  <span>Progress</span>
                  <span className="tabular-nums font-medium">{jobPctNum}%</span>
                </div>
                <div className="h-2 rounded-full bg-blue-200/80 dark:bg-blue-900/80 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-blue-600 dark:bg-blue-500 transition-[width] duration-300"
                    style={{ width: `${jobPctNum}%` }}
                  />
                </div>
              </div>
            ) : null}
            <p className="text-sm text-blue-950 dark:text-blue-50 leading-relaxed">{jobMsg}</p>
          </div>
        ) : null}
        <div>
          <button
            type="button"
            onClick={() => void generate()}
            disabled={nQuestions === 0}
            className="w-full rounded-xl bg-blue-600 hover:bg-blue-700 text-white px-4 py-3.5 text-[15px] font-semibold shadow-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none"
          >
            Write draft answers with AI
          </button>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-2 text-center leading-relaxed">
            Uses your{" "}
            <Link to="/org" className="text-blue-600 dark:text-blue-400 underline underline-offset-2">
              organization profile
            </Link>
            . Runs on this computer; may take a few minutes.
          </p>
        </div>

        <div className="pt-1 border-t border-slate-100 dark:border-slate-800">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
            Download
          </p>
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => void exportGrantFormat("qa_pdf")}
              disabled={nQuestions === 0}
              className="rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 py-2.5 text-xs font-medium text-slate-800 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700/80 disabled:opacity-40"
            >
              PDF
            </button>
            <button
              type="button"
              onClick={() => void exportGrantFormat("markdown")}
              disabled={nQuestions === 0}
              className="rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 py-2.5 text-xs font-medium text-slate-800 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700/80 disabled:opacity-40"
            >
              Markdown
            </button>
            <button
              type="button"
              onClick={() => void exportGrantFormat("docx")}
              disabled={nQuestions === 0}
              className="rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 py-2.5 text-xs font-medium text-slate-800 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700/80 disabled:opacity-40"
            >
              Word
            </button>
          </div>
        </div>

        {nQuestions > 0 ? (
          <div className="pt-1 border-t border-slate-100 dark:border-slate-800">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
              Organization memory
            </p>
            <p className="text-xs text-slate-600 dark:text-slate-400 mb-3 leading-relaxed">
              Save reusable facts from your answers to your profile for the next grant.
            </p>
            <button
              type="button"
              onClick={() => void learnFromAnswers()}
              className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-transparent py-2.5 text-sm font-medium text-slate-800 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800/80"
            >
              Learn from these answers
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );

  return (
    <div>
      {/* Page header — full width */}
      <header className="mb-8 pb-6 border-b border-slate-200/90 dark:border-slate-800">
        <Link
          to="/"
          className="text-sm text-slate-600 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
        >
          ← All grants
        </Link>
        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-slate-900 dark:text-white">
              {grant.name}
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1.5">
              {grantStatusLabel(grant.status)}
              {nQuestions > 0
                ? ` · ${nQuestions} question${nQuestions === 1 ? "" : "s"}`
                : " · No questions yet"}
            </p>
          </div>
          <button
            type="button"
            onClick={removeGrant}
            className="text-sm text-slate-500 hover:text-red-600 dark:text-slate-400 dark:hover:text-red-400 shrink-0 self-start"
          >
            Delete grant
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-6 rounded-xl bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-200 px-4 py-3 text-sm border border-red-200/80 dark:border-red-900/40">
          {error}
        </div>
      )}

      {/* Mobile: actions first; desktop: main | sticky sidebar — job progress lives in sidebar */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_300px] xl:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
        <aside className="order-1 lg:order-2 lg:sticky lg:top-20 lg:self-start">{actionPanel}</aside>

        <div className="order-2 lg:order-1 space-y-10 min-w-0">
          <section className="space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Application source</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-2xl leading-relaxed">
                Upload a PDF or Word file from the funder, or paste a link to the public application page.
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-5">
              <div className="rounded-2xl border border-slate-200/90 dark:border-slate-700 p-5 space-y-4 bg-white dark:bg-slate-900/40">
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">File upload</h3>
                <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                  {grant.file_name ? (
                    <>
                      Current file: <span className="text-slate-900 dark:text-slate-200">{grant.file_name}</span>
                    </>
                  ) : (
                    "No file selected."
                  )}
                </p>
                <input
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  disabled={uploading}
                  onChange={(e) => onUpload(e.target.files?.[0] ?? null)}
                  className="text-sm w-full file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm dark:file:bg-slate-700"
                />
                <button
                  type="button"
                  onClick={() => void parseFromFile()}
                  disabled={!grant.source_file_key}
                  className="w-full rounded-xl bg-slate-900 dark:bg-white text-white dark:text-slate-900 py-2.5 text-sm font-medium disabled:opacity-40"
                >
                  Find questions in file
                </button>
              </div>

              <div className="rounded-2xl border border-slate-200/90 dark:border-slate-700 p-5 space-y-4 bg-white dark:bg-slate-900/40">
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Web page</h3>
                <input
                  type="url"
                  className="w-full rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2.5 text-sm"
                  placeholder="https://…"
                  value={urlDraft}
                  onChange={(e) => setUrlDraft(e.target.value)}
                />
                <div className="flex flex-col sm:flex-row gap-2">
                  <button
                    type="button"
                    onClick={() => void previewWeb()}
                    disabled={previewLoading || !urlDraft.trim()}
                    className="rounded-xl border border-slate-200 dark:border-slate-600 px-4 py-2 text-sm font-medium disabled:opacity-40"
                  >
                    {previewLoading ? "Loading…" : "Preview"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void parseFromWeb()}
                    disabled={!urlDraft.trim()}
                    className="flex-1 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-2 text-sm font-medium disabled:opacity-40"
                  >
                    Find questions on page
                  </button>
                </div>
                {previewText !== null && (
                  <div className="rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-100 dark:border-slate-700 p-3 max-h-36 overflow-y-auto text-xs text-slate-700 dark:text-slate-300 whitespace-pre-wrap font-sans">
                    {previewText}
                  </div>
                )}
                <details className="text-xs text-slate-500">
                  <summary className="cursor-pointer hover:text-slate-700 dark:hover:text-slate-300">
                    Link troubleshooting
                  </summary>
                  <ul className="mt-2 list-disc pl-4 space-y-1 text-slate-600 dark:text-slate-400">
                    <li>Login-only or interactive pages often won&apos;t work — try a PDF.</li>
                    <li>Public pages only.</li>
                  </ul>
                </details>
              </div>
            </div>
          </section>

          <section className="space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Questions &amp; answers</h2>
              {nQuestions === 0 ? (
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-2 max-w-2xl leading-relaxed">
                  Questions appear here after you find them from a file or web page.
                </p>
              ) : null}
            </div>
            {nQuestions > 0
              ? grant.questions.map((q) => (
                  <QuestionCard
                    key={q.question_id}
                    q={q}
                    a={answerFor(grant.answers, q.question_id)}
                    onSave={(v) => patchAnswer(q, v)}
                    onReview={(r) => toggleReviewed(q, r)}
                    onMarkDirty={() => setAnswersDirty(true)}
                  />
                ))
              : null}
          </section>
        </div>
      </div>
    </div>
  );
}

function QuestionCard({
  q,
  a,
  onSave,
  onReview,
  onMarkDirty,
}: {
  q: Question;
  a: Answer | undefined;
  onSave: (v: unknown) => void | Promise<void>;
  onReview: (r: boolean) => void;
  onMarkDirty: () => void;
}) {
  const typeLabel = questionTypeLabel(q.type);
  return (
    <div className="rounded-2xl border border-slate-200/90 dark:border-slate-700 p-5 bg-white dark:bg-slate-900/40 space-y-4 shadow-sm dark:shadow-none">
      <div className="text-xs text-slate-500 dark:text-slate-400 flex flex-wrap gap-x-2 gap-y-1">
        <span className="font-medium text-slate-600 dark:text-slate-300">{typeLabel}</span>
        {q.required ? <span>· Required</span> : null}
        {a?.needs_manual_input ? (
          <span className="text-amber-700 dark:text-amber-400">· Needs your input</span>
        ) : null}
      </div>
      <div className="font-medium text-slate-900 dark:text-white leading-snug text-[15px]">{q.question_text}</div>
      <QuestionAnswerField q={q} a={a} onSave={onSave} onUserEdit={onMarkDirty} />
      <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300 cursor-pointer pt-1">
        <input
          type="checkbox"
          checked={a?.reviewed ?? false}
          onChange={(e) => onReview(e.target.checked)}
        />
        Mark as reviewed
      </label>
    </div>
  );
}
