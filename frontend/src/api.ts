import { humanizeApiError } from "./errors";

const BASE = "";

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const body = init?.body;
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  // FormData must not use Content-Type: application/json — the browser sets multipart + boundary.
  const r = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(body && !isFormData ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const j = (await r.json()) as { detail?: string | Array<{ msg?: string }> };
      if (typeof j.detail === "string") detail = j.detail;
      else if (Array.isArray(j.detail) && j.detail[0]?.msg) detail = j.detail[0].msg;
    } catch {
      /* ignore */
    }
    throw new Error(humanizeApiError(detail));
  }
  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}

export type GrantSummary = {
  id: string;
  name: string;
  status: string;
  source_type: string;
  created_at: string;
  updated_at: string;
};

export type Question = {
  question_id: string;
  question_text: string;
  type: string;
  options: string[];
  required: boolean;
  char_limit: number | null;
  sort_order: number;
};

export type Answer = {
  question_id: string;
  answer_value: unknown;
  reviewed: boolean;
  needs_manual_input: boolean;
  evidence_fact_ids: string[];
};

export type GrantDetail = GrantSummary & {
  grant_url: string | null;
  portal_url: string | null;
  source_file_key: string | null;
  file_name: string | null;
  export_file_key: string | null;
  questions: Question[];
  answers: Answer[];
};

export type Org = {
  id: string;
  legal_name: string;
  mission_short: string;
  mission_long: string;
  address: string;
  extra_sections: { id: string; title: string; content: string }[];
};

export type Fact = {
  id: string;
  org_id: string;
  key: string;
  value: string;
  source: string;
  updated_at: string | null;
};

export type Job = {
  id: string;
  grant_id: string | null;
  job_kind: string;
  status: string;
  progress: number;
  error: string | null;
  result_json: Record<string, unknown> | null;
  created_at: string;
};

export const api = {
  health: () => json<{ ok: boolean }>("/api/v1/health"),
  config: () =>
    json<{ ollama_configured: boolean; default_model: string; data_dir: string }>("/api/v1/config"),
  getOrg: () => json<Org>("/api/v1/org"),
  putOrg: (body: Partial<Org>) =>
    json<Org>("/api/v1/org", { method: "PUT", body: JSON.stringify(body) }),
  listFacts: () => json<Fact[]>("/api/v1/org/facts"),
  createFact: (body: { key: string; value: string; source?: string }) =>
    json<Fact>("/api/v1/org/facts", { method: "POST", body: JSON.stringify(body) }),
  updateFact: (id: string, body: Partial<{ key: string; value: string; source: string }>) =>
    json<Fact>(`/api/v1/org/facts/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteFact: (id: string) => json<{ ok: boolean }>(`/api/v1/org/facts/${id}`, { method: "DELETE" }),
  listGrants: () => json<GrantSummary[]>("/api/v1/grants"),
  createGrant: (body: { name: string; grant_url?: string; source_type?: string }) =>
    json<GrantDetail>("/api/v1/grants", { method: "POST", body: JSON.stringify(body) }),
  getGrant: (id: string) => json<GrantDetail>(`/api/v1/grants/${id}`),
  putGrant: (
    id: string,
    body: Partial<{ name: string; grant_url: string | null; portal_url: string | null; status: string }>
  ) => json<GrantDetail>(`/api/v1/grants/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteGrant: (id: string) => json<{ ok: boolean }>(`/api/v1/grants/${id}`, { method: "DELETE" }),
  uploadFile: (grantId: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return json<{ file_key: string; file_name: string }>(`/api/v1/grants/${grantId}/files`, {
      method: "POST",
      body: fd,
    });
  },
  parse: (grantId: string, body: { file_key?: string; use_url?: boolean; url?: string | null }) =>
    json<{ job_id: string }>(`/api/v1/grants/${grantId}/parse`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  previewUrl: (
    grantId: string,
    body: { url?: string | null }
  ): Promise<{ preview: string; char_count: number; meta: Record<string, unknown> }> =>
    json(`/api/v1/grants/${grantId}/preview-url`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  generate: (grantId: string, question_ids?: string[]) =>
    json<{ job_id: string }>(`/api/v1/grants/${grantId}/generate`, {
      method: "POST",
      body: JSON.stringify({ question_ids: question_ids ?? null }),
    }),
  exportGrant: (grantId: string, format: "qa_pdf" | "markdown" | "docx" = "qa_pdf") =>
    json<{ file_key: string; download_path: string }>(`/api/v1/grants/${grantId}/export`, {
      method: "POST",
      body: JSON.stringify({ format }),
    }),
  learnOrgFromGrant: (grantId: string) =>
    json<{ job_id: string; status: string }>(`/api/v1/grants/${grantId}/learn-org`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  patchAnswer: (
    grantId: string,
    questionId: string,
    body: { answer_value?: unknown; reviewed?: boolean }
  ) =>
    json<Answer>(`/api/v1/grants/${grantId}/questions/${questionId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  getJob: (jobId: string) => json<Job>(`/api/v1/jobs/${jobId}`),
  fileUrl: (fileKey: string) => `${BASE}/api/v1/files/${encodeURI(fileKey)}`,
};
