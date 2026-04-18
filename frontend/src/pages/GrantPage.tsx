import {
  DndContext,
  DragCancelEvent,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useBlocker, useNavigate, useParams } from "react-router-dom";
import { QuestionAnswerField } from "../components/QuestionAnswerField";
import { grantStatusLabel, questionTypeLabel } from "../copy";
import { humanizeApiError } from "../errors";
import { api, type Answer, type GrantDetail, type Question } from "../api";
import { answerSufficientForReview } from "../utils/answerReview";
import {
  answerValuesEqual,
  isGrantWorkspaceDirty,
  mergeAnswerForDisplay,
  serverAnswerValue,
  urlFromGrant,
} from "../utils/grantWorkspace";
import { formatLabelDisplay, formatQuestionLabels } from "../utils/questionLabels";
import { questionDomId } from "../utils/questionDomId";
import { downloadExportedFile } from "../utils/downloadFile";

function answerHasContent(a: Answer | undefined): boolean {
  if (!a) return false;
  const v = a.answer_value;
  if (v == null) return false;
  if (typeof v === "string") {
    const s = v.trim();
    if (!s || s.toUpperCase() === "INSUFFICIENT_INFO") return false;
    return true;
  }
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === "number" || typeof v === "boolean") return true;
  return false;
}

/** True if re-parsing would wipe existing questions and/or filled answers. */
function parseWouldReplaceExisting(grant: GrantDetail): boolean {
  if (grant.questions.length > 0) return true;
  return grant.answers.some(answerHasContent);
}

export function GrantPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [grant, setGrant] = useState<GrantDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobMsg, setJobMsg] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [urlDraft, setUrlDraft] = useState("");
  const [draftAnswerValues, setDraftAnswerValues] = useState<Record<string, unknown>>({});
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [previewWarnings, setPreviewWarnings] = useState<string[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [saveHint, setSaveHint] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reorderBusy, setReorderBusy] = useState(false);
  const [activeDragId, setActiveDragId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
      disabled: reorderBusy,
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
      disabled: reorderBusy,
    })
  );

  const workspaceDirty = useMemo(
    () => (grant ? isGrantWorkspaceDirty(grant, nameDraft, urlDraft, draftAnswerValues) : false),
    [grant, nameDraft, urlDraft, draftAnswerValues]
  );

  const blocker = useBlocker(workspaceDirty);
  const blockerHandling = useRef(false);

  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if (blockerHandling.current) return;
    blockerHandling.current = true;
    const ok = window.confirm("You have unsaved changes. Leave without saving?");
    if (ok) blocker.proceed();
    else blocker.reset();
    blockerHandling.current = false;
  }, [blocker]);

  const load = useCallback(() => {
    if (!id) return;
    api
      .getGrant(id)
      .then(setGrant)
      .catch((e: Error) => setError(humanizeApiError(e)));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (!workspaceDirty) return;
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [workspaceDirty]);

  useEffect(() => {
    if (!grant) return;
    setNameDraft(grant.name);
    setUrlDraft(urlFromGrant(grant));
    setDraftAnswerValues({});
  }, [grant?.id]);

  const questionIdSig = grant?.questions.map((q) => q.question_id).join("|") ?? "";
  useEffect(() => {
    if (!grant) return;
    setDraftAnswerValues((prev) => {
      const ids = new Set(grant.questions.map((q) => q.question_id));
      const next = { ...prev };
      let changed = false;
      for (const k of Object.keys(next)) {
        if (!ids.has(k)) {
          delete next[k];
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [grant?.id, questionIdSig]);

  const discardLocalWorkspace = useCallback(() => {
    if (!grant) return;
    setNameDraft(grant.name);
    setUrlDraft(urlFromGrant(grant));
    setDraftAnswerValues({});
  }, [grant]);

  const updateAnswerDraft = useCallback(
    (q: Question, value: unknown) => {
      if (!grant) return;
      setDraftAnswerValues((prev) => {
        const serverVal = serverAnswerValue(grant, q.question_id);
        const next = { ...prev };
        if (answerValuesEqual(q.type, value, serverVal)) {
          delete next[q.question_id];
        } else {
          next[q.question_id] = value;
        }
        return next;
      });
    },
    [grant]
  );

  async function pollJob(jobId: string, label: string) {
    let consecutiveErrors = 0;
    for (let i = 0; i < 600; i++) {
      try {
        const j = await api.getJob(jobId);
        consecutiveErrors = 0;
        if (j.status === "completed") {
          if (j.job_kind === "parse" || j.job_kind === "generate") {
            setDraftAnswerValues({});
          }
          if (j.job_kind === "learn_org" && j.result_json && typeof j.result_json === "object") {
            const r = j.result_json as {
              facts_added?: number;
              facts_updated?: number;
              facts_skipped_similar?: number;
            };
            const a = r.facts_added ?? 0;
            const u = r.facts_updated ?? 0;
            const sk = r.facts_skipped_similar ?? 0;
            const skipPart =
              sk > 0
                ? ` ${sk} near-duplicate${sk === 1 ? "" : "s"} skipped (already covered in your profile).`
                : "";
            setJobMsg(
              `Organization profile updated: ${a} new fact${a === 1 ? "" : "s"}, ${u} updated.${skipPart} View them under Your organization.`
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

  async function saveWorkspace() {
    if (!id || !grant || saving) return;
    if (!workspaceDirty) return;
    if (!window.confirm("Save changes to this application?")) return;
    const trimmedName = nameDraft.trim();
    if (!trimmedName) {
      setError("Grant name cannot be empty.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const body: Partial<{ name: string; grant_url: string | null; portal_url: string | null }> = {};
      if (trimmedName !== grant.name.trim()) body.name = trimmedName;
      const urlTrim = urlDraft.trim();
      const serverUrl = urlFromGrant(grant).trim();
      if (urlTrim !== serverUrl) {
        body.grant_url = urlTrim || null;
        body.portal_url = null;
      }

      let meta = grant;
      if (Object.keys(body).length > 0) {
        meta = await api.putGrant(id, body);
        setGrant(meta);
      }

      for (const q of meta.questions) {
        const draft = draftAnswerValues[q.question_id];
        if (draft === undefined) continue;
        if (answerValuesEqual(q.type, draft, serverAnswerValue(meta, q.question_id))) continue;
        await api.patchAnswer(id, q.question_id, { answer_value: draft });
      }

      const loaded = await api.getGrant(id);
      setGrant(loaded);
      setNameDraft(loaded.name);
      setUrlDraft(urlFromGrant(loaded));
      setDraftAnswerValues({});
      setSaveHint("Saved.");
      window.setTimeout(() => setSaveHint(null), 2500);
    } catch (e) {
      setError(humanizeApiError(e));
    } finally {
      setSaving(false);
    }
  }

  async function onUpload(file: File | null) {
    if (!id || !file) return;
    if (workspaceDirty) {
      const ok = window.confirm(
        "You have unsaved changes. Uploading replaces the file on the server and will reload this grant. Discard unsaved edits and continue?"
      );
      if (!ok) return;
      discardLocalWorkspace();
    }
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
    if (!id || !grant) return;
    if (workspaceDirty) {
      const ok = window.confirm(
        "You have unsaved changes. Finding questions again may replace your current work. Discard unsaved edits and continue?"
      );
      if (!ok) return;
      discardLocalWorkspace();
    }
    if (parseWouldReplaceExisting(grant)) {
      const ok = window.confirm(
        "Finding questions again will replace all current questions and answers for this grant. Use Duplicate grant (in the header) to keep a full backup, or export first. Continue?"
      );
      if (!ok) return;
    }
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

  const urlOutOfSync =
    grant != null && urlDraft.trim() !== urlFromGrant(grant).trim();

  async function parseFromWeb() {
    if (!id || !grant) return;
    const u = urlDraft.trim();
    if (!u) {
      setError("Paste the web address of the application page first.");
      return;
    }
    if (urlOutOfSync) {
      setError("Save your link changes before finding questions on the page.");
      return;
    }
    if (workspaceDirty) {
      const ok = window.confirm(
        "You have unsaved changes. Finding questions again may replace your current work. Discard unsaved edits and continue?"
      );
      if (!ok) return;
      discardLocalWorkspace();
    }
    if (parseWouldReplaceExisting(grant)) {
      const ok = window.confirm(
        "Finding questions again will replace all current questions and answers for this grant. Use Duplicate grant (in the header) to keep a full backup, or export first. Continue?"
      );
      if (!ok) return;
    }
    setError(null);
    setJobMsg("Finding questions on the web page…");
    try {
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
    if (urlOutOfSync) {
      setError("Save your link changes before previewing.");
      return;
    }
    setError(null);
    setPreviewLoading(true);
    setPreviewText(null);
    setPreviewWarnings([]);
    try {
      const res = await api.previewUrl(id, { url: u });
      setPreviewText(res.preview);
      setPreviewWarnings(Array.isArray(res.warnings) ? res.warnings : []);
    } catch (e) {
      setError(humanizeApiError(e));
    } finally {
      setPreviewLoading(false);
    }
  }

  async function learnFromAnswers() {
    if (!id) return;
    if (workspaceDirty) {
      setError("Save your changes before updating organization facts.");
      return;
    }
    const ok = window.confirm(
      "This will add or update reusable organization facts from the answers on this grant. Review and edit facts under Your organization afterward. Continue?"
    );
    if (!ok) return;
    setError(null);
    setJobMsg("Updating organization facts from answers…");
    try {
      const { job_id } = await api.learnOrgFromGrant(id);
      await pollJob(job_id, "Updating organization facts");
    } catch (e) {
      setJobMsg(null);
      setError(humanizeApiError(e));
    }
  }

  async function generate() {
    if (!id) return;
    if (workspaceDirty) {
      setError("Save your changes before generating draft answers.");
      return;
    }
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
    if (workspaceDirty) {
      setError("Save your changes before exporting — the download reflects saved data only.");
      return;
    }
    setError(null);
    try {
      const { download_path, filename } = await api.exportGrant(id, format);
      await downloadExportedFile(download_path, filename);
      load();
    } catch (e) {
      setError(humanizeApiError(e));
    }
  }

  async function toggleReviewed(q: Question, reviewed: boolean) {
    if (!id) return;
    setError(null);
    try {
      await api.patchAnswer(id, q.question_id, { reviewed });
      await load();
    } catch (e) {
      setError(humanizeApiError(e));
    }
  }

  async function persistQuestionOrder(ordered: Question[]) {
    if (!id || !grant) return;
    const snapshot = grant;
    const optimistic: GrantDetail = {
      ...grant,
      questions: ordered.map((q, i) => ({ ...q, sort_order: i })),
    };
    setGrant(optimistic);
    setReorderBusy(true);
    setError(null);
    try {
      const updated = await api.reorderQuestions(
        id,
        ordered.map((x) => x.question_id)
      );
      setGrant(updated);
    } catch (e) {
      setError(humanizeApiError(e));
      setGrant(snapshot);
    } finally {
      setReorderBusy(false);
    }
  }

  function onQuestionsDragStart(event: DragStartEvent) {
    setActiveDragId(String(event.active.id));
  }

  function onQuestionsDragCancel(_event: DragCancelEvent) {
    setActiveDragId(null);
  }

  function onQuestionsDragEnd(event: DragEndEvent) {
    setActiveDragId(null);
    if (!grant || reorderBusy) return;
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const items = grant.questions;
    const oldIndex = items.findIndex((x) => x.question_id === String(active.id));
    const newIndex = items.findIndex((x) => x.question_id === String(over.id));
    if (oldIndex < 0 || newIndex < 0) return;
    const next = arrayMove(items, oldIndex, newIndex);
    void persistQuestionOrder(next);
  }

  async function duplicateGrant() {
    if (!id || !grant) return;
    const includeQa = window.confirm(
      "Include a copy of questions and answers?\n\nOK = duplicate everything (full backup).\nCancel = copy file and indexed application text only (good if you want to re-parse safely)."
    );
    const defaultName = `${grant.name} (copy)`;
    const name = window.prompt("Name for the new grant (optional):", defaultName);
    if (name === null) return;
    setError(null);
    try {
      const g = await api.duplicateGrant(id, {
        name: name.trim() || undefined,
        include_qa: includeQa,
      });
      navigate(`/grants/${g.id}`);
    } catch (e) {
      setError(humanizeApiError(e));
    }
  }

  async function removeGrant() {
    if (!id) return;
    const msg = workspaceDirty
      ? "You have unsaved changes. Delete this grant and its files anyway?"
      : "Delete this grant and its files?";
    if (!confirm(msg)) return;
    await api.deleteGrant(id);
    navigate("/", { replace: true });
  }

  useEffect(() => {
    if (!grant?.questions?.length) return;
    const raw = window.location.hash.replace(/^#/, "");
    if (!raw) return;
    const el = document.getElementById(raw);
    if (!el) return;
    const t = window.setTimeout(() => {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
    return () => window.clearTimeout(t);
  }, [grant?.id, grant?.questions?.length]);

  if (!id) return null;
  if (!grant) {
    return <p className="text-slate-500">Loading…</p>;
  }

  const nQuestions = grant.questions.length;
  const questionLabels = formatQuestionLabels(grant.questions.map((q) => q.question_text));

  const saveStatusLine = saveHint ? (
    <span className="text-emerald-700 dark:text-emerald-400 font-medium">{saveHint}</span>
  ) : workspaceDirty ? (
    <span className="text-amber-800 dark:text-amber-300">
      Unsaved changes — use Save in the header before leaving or running AI/export.
    </span>
  ) : nQuestions > 0 ? (
    <span className="text-slate-500 dark:text-slate-400">All changes saved.</span>
  ) : (
    <span className="text-slate-500 dark:text-slate-400">Add a file or link below, then find questions.</span>
  );

  const jobPct = jobMsg?.match(/(\d+)%/)?.[1];
  const jobPctNum = jobPct != null ? Math.min(100, Math.max(0, parseInt(jobPct, 10))) : null;

  const webPreviewDisabled = previewLoading || !urlDraft.trim() || urlOutOfSync;
  const webParseDisabled = !urlDraft.trim() || urlOutOfSync;

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
            Uses your saved{" "}
            <Link to="/org" className="text-blue-600 dark:text-blue-400 underline underline-offset-2">
              organization facts
            </Link>{" "}
            and indexed text from this application after you run Find questions. Runs on this computer; may take a few
            minutes.
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
      <header className="mb-8 pb-6 border-b border-slate-200/90 dark:border-slate-800">
        <Link
          to="/"
          className="text-sm text-slate-600 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
        >
          ← All grants
        </Link>
        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 flex-1 space-y-3">
            <label className="block">
              <span className="sr-only">Grant name</span>
              <input
                type="text"
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
                className="w-full max-w-xl text-2xl sm:text-3xl font-semibold tracking-tight text-slate-900 dark:text-white bg-transparent border border-transparent hover:border-slate-200 dark:hover:border-slate-600 focus:border-blue-500 rounded-lg px-2 py-1 -mx-2"
              />
            </label>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {grantStatusLabel(grant.status)}
              {nQuestions > 0
                ? ` · ${nQuestions} question${nQuestions === 1 ? "" : "s"}`
                : " · No questions yet"}
            </p>
          </div>
          <div className="flex flex-wrap gap-3 shrink-0 self-start items-center">
            <button
              type="button"
              onClick={() => void saveWorkspace()}
              disabled={!workspaceDirty || saving}
              aria-busy={saving}
              className="rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-2.5 text-sm font-semibold shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              onClick={() => void duplicateGrant()}
              className="text-sm font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
            >
              Duplicate grant
            </button>
            <button
              type="button"
              onClick={removeGrant}
              className="text-sm text-slate-500 hover:text-red-600 dark:text-slate-400 dark:hover:text-red-400"
            >
              Delete grant
            </button>
          </div>
        </div>
      </header>

      {error && (
        <div className="mb-6 rounded-xl bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-200 px-4 py-3 text-sm border border-red-200/80 dark:border-red-900/40">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_300px] xl:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
        <aside className="order-1 lg:order-2 lg:sticky lg:top-20 lg:self-start">{actionPanel}</aside>

        <div className="order-2 lg:order-1 space-y-10 min-w-0">
          <section className="space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Application source</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-2xl leading-relaxed">
                Upload a PDF or Word file from the funder, or paste a link to the public application page. Login-only
                and multi-step online forms work best if you export or print the form as PDF and upload that instead.
              </p>
              {(grant.source_chunk_count ?? 0) > 0 ? (
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
                  Indexed {grant.source_chunk_count} text segment
                  {grant.source_chunk_count === 1 ? "" : "s"} from this application for AI drafting.
                </p>
              ) : null}
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
                {urlOutOfSync ? (
                  <p className="text-xs text-amber-800 dark:text-amber-200/90">
                    Save your changes (header) before previewing or finding questions on this link.
                  </p>
                ) : null}
                <div className="flex flex-col sm:flex-row gap-2">
                  <button
                    type="button"
                    onClick={() => void previewWeb()}
                    disabled={webPreviewDisabled}
                    className="rounded-xl border border-slate-200 dark:border-slate-600 px-4 py-2 text-sm font-medium disabled:opacity-40"
                  >
                    {previewLoading ? "Loading…" : "Preview"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void parseFromWeb()}
                    disabled={webParseDisabled}
                    className="flex-1 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-2 text-sm font-medium disabled:opacity-40"
                  >
                    Find questions on page
                  </button>
                </div>
                {previewWarnings.length > 0 ? (
                  <div className="rounded-xl border border-amber-200/90 dark:border-amber-800/60 bg-amber-50/90 dark:bg-amber-950/40 px-3 py-2.5 text-xs text-amber-950 dark:text-amber-100 space-y-1.5">
                    <p className="font-semibold text-amber-900 dark:text-amber-200">Heads up</p>
                    <ul className="list-disc pl-4 space-y-1 text-amber-900/95 dark:text-amber-100/95">
                      {previewWarnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {previewText !== null ? (
                  <div className="rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-100 dark:border-slate-700 p-3 max-h-36 overflow-y-auto text-xs text-slate-700 dark:text-slate-300 whitespace-pre-wrap font-sans">
                    {previewText}
                  </div>
                ) : null}
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
              ) : (
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-2 max-w-2xl leading-relaxed">
                  Drag the handle beside each number to change order. Numbers update automatically.
                </p>
              )}
            </div>
            {nQuestions > 0 ? (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragStart={onQuestionsDragStart}
                onDragCancel={onQuestionsDragCancel}
                onDragEnd={onQuestionsDragEnd}
              >
                <SortableContext
                  items={grant.questions.map((q) => q.question_id)}
                  strategy={verticalListSortingStrategy}
                >
                  {grant.questions.map((q, index) => {
                    const merged = mergeAnswerForDisplay(grant, q.question_id, draftAnswerValues[q.question_id]);
                    return (
                      <SortableQuestionCard
                        key={q.question_id}
                        q={q}
                        displayLabel={questionLabels[index] ?? String(index + 1)}
                        a={merged}
                        onValueChange={(v) => updateAnswerDraft(q, v)}
                        onReview={(r) => void toggleReviewed(q, r)}
                        onMarkReviewBlocked={() => setError("Add an answer before marking as reviewed.")}
                        reorderDisabled={reorderBusy || nQuestions < 2}
                      />
                    );
                  })}
                </SortableContext>
                <DragOverlay adjustScale={false} className="z-40" dropAnimation={null}>
                  {activeDragId
                    ? (() => {
                        const idx = grant.questions.findIndex((x) => x.question_id === activeDragId);
                        if (idx < 0) return null;
                        const q = grant.questions[idx];
                        const merged = mergeAnswerForDisplay(grant, q.question_id, draftAnswerValues[q.question_id]);
                        const displayLabel = questionLabels[idx] ?? String(idx + 1);
                        return (
                          <div className="rounded-2xl border border-slate-200/90 dark:border-slate-700 bg-white dark:bg-slate-900/95 p-5 shadow-2xl ring-2 ring-slate-900/10 dark:ring-white/10 max-w-[min(100vw-2rem,42rem)] cursor-grabbing">
                            <QuestionCardInner
                              q={q}
                              a={merged}
                              displayLabel={displayLabel}
                              onValueChange={() => {}}
                              onReview={() => {}}
                              onMarkReviewBlocked={() => {}}
                              reorderDisabled
                              dragHandle={null}
                              isOverlay
                            />
                          </div>
                        );
                      })()
                    : null}
                </DragOverlay>
              </DndContext>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  );
}

type SortableDragHandle = Pick<ReturnType<typeof useSortable>, "attributes" | "listeners">;

function QuestionCardInner({
  q,
  a,
  displayLabel,
  onValueChange,
  onReview,
  onMarkReviewBlocked,
  reorderDisabled,
  dragHandle,
  isOverlay,
}: {
  q: Question;
  a: Answer | undefined;
  displayLabel: string;
  onValueChange: (v: unknown) => void;
  onReview: (r: boolean) => void | Promise<void>;
  onMarkReviewBlocked: () => void;
  reorderDisabled: boolean;
  dragHandle: SortableDragHandle | null;
  isOverlay: boolean;
}) {
  const typeLabel = questionTypeLabel(q.type);
  const blockInteraction = isOverlay;

  return (
    <div
      className={blockInteraction ? "space-y-4 pointer-events-none select-none" : "space-y-4"}
    >
      <div className="flex gap-3 items-start">
        <button
          type="button"
          className={
            isOverlay
              ? "mt-0.5 shrink-0 rounded-md border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 px-1.5 py-1 text-slate-500 dark:text-slate-400 cursor-grabbing touch-none opacity-80"
              : "mt-0.5 shrink-0 rounded-md border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 px-1.5 py-1 text-slate-500 dark:text-slate-400 cursor-grab active:cursor-grabbing touch-none disabled:opacity-40 disabled:cursor-not-allowed"
          }
          aria-label="Drag to reorder question"
          disabled={reorderDisabled || isOverlay}
          {...(dragHandle ? dragHandle.attributes : {})}
          {...(dragHandle ? dragHandle.listeners : {})}
        >
          <span aria-hidden className="text-base leading-none font-bold tracking-tighter">
            ⋮⋮
          </span>
        </button>
        <div className="min-w-0 flex-1 space-y-4">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="text-sm font-semibold text-slate-700 dark:text-slate-200 tabular-nums shrink-0">
              {formatLabelDisplay(displayLabel)}
            </span>
            <div className="text-xs text-slate-500 dark:text-slate-400 flex flex-wrap gap-x-2 gap-y-1">
              <span className="font-medium text-slate-600 dark:text-slate-300">{typeLabel}</span>
              {q.required ? <span>· Required</span> : null}
              {(q.type === "single_choice" || q.type === "multi_choice") &&
              (!q.options || q.options.length === 0) ? (
                <span className="text-amber-800 dark:text-amber-300 font-medium">
                  · No choices detected — pick or type an answer that matches the real form
                </span>
              ) : null}
              {a?.needs_manual_input ? (
                <span className="text-amber-700 dark:text-amber-400">· Needs your input</span>
              ) : null}
            </div>
          </div>
          <div className="font-medium text-slate-900 dark:text-white leading-snug text-[15px]">{q.question_text}</div>
          <QuestionAnswerField q={q} a={a} onValueChange={onValueChange} />
          <label
            className={`flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300 pt-1 ${
              blockInteraction ? "" : "cursor-pointer"
            }`}
          >
            <input
              type="checkbox"
              checked={a?.reviewed ?? false}
              readOnly={blockInteraction}
              tabIndex={blockInteraction ? -1 : undefined}
              onChange={(e) => {
                if (blockInteraction) return;
                const checked = e.target.checked;
                if (checked && !answerSufficientForReview(q, a)) {
                  onMarkReviewBlocked();
                  return;
                }
                void onReview(checked);
              }}
            />
            Mark as reviewed
          </label>
        </div>
      </div>
    </div>
  );
}

function SortableQuestionCard({
  q,
  a,
  displayLabel,
  onValueChange,
  onReview,
  onMarkReviewBlocked,
  reorderDisabled,
}: {
  q: Question;
  a: Answer | undefined;
  displayLabel: string;
  onValueChange: (v: unknown) => void;
  onReview: (r: boolean) => void | Promise<void>;
  onMarkReviewBlocked: () => void;
  reorderDisabled: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: q.question_id,
    disabled: reorderDisabled,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition: isDragging ? undefined : transition,
    opacity: isDragging ? 0 : 1,
    position: "relative" as const,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      id={questionDomId(q.question_id)}
      className="rounded-2xl border border-slate-200/90 dark:border-slate-700 p-5 bg-white dark:bg-slate-900/40 shadow-sm dark:shadow-none scroll-mt-24"
    >
      <QuestionCardInner
        q={q}
        a={a}
        displayLabel={displayLabel}
        onValueChange={onValueChange}
        onReview={onReview}
        onMarkReviewBlocked={onMarkReviewBlocked}
        reorderDisabled={reorderDisabled}
        dragHandle={{ attributes, listeners }}
        isOverlay={false}
      />
    </div>
  );
}
