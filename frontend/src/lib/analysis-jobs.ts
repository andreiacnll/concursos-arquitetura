import { API_URL } from "@/lib/api";

export type AnalysisJobStatus =
  | "queued"
  | "processing"
  | "completed"
  | "partial"
  | "failed"
  | "cancelled"
  | "interrupted";

export type AnalysisJobState = {
  id?: number;
  job_id: number;
  concurso_id: number;
  status: AnalysisJobStatus;
  stage?: string | null;
  progress?: number | null;
  analysis_id?: number | null;
  error?: string | null;
  updated_at?: string | null;
};

export const ANALYSIS_POLL_INTERVAL_MS = 2500;
export const ANALYSIS_POLL_TIMEOUT_MS = 5 * 60 * 1000;

export function isTerminalAnalysisStatus(status?: string | null): boolean {
  return ["completed", "partial", "failed", "cancelled", "interrupted"].includes(
    status || "",
  );
}

export function isActiveAnalysisStatus(status?: string | null): boolean {
  return status === "queued" || status === "processing";
}

function normalizeStatus(value: unknown): AnalysisJobStatus {
  const status = String(value || "").toLowerCase();
  if (status === "completed" || status === "concluida") return "completed";
  if (status === "partial") return "partial";
  if (status === "failed" || status === "erro") return "failed";
  if (status === "cancelled" || status === "cancelada") return "cancelled";
  if (status === "interrupted") return "interrupted";
  if (status === "queued" || status === "aguarda") return "queued";
  return "processing";
}

export function normalizeAnalysisJob(raw: any): AnalysisJobState | null {
  const jobId = Number(raw?.job_id ?? raw?.id);
  const concursoId = Number(raw?.concurso_id ?? raw?.competition_id);
  if (!Number.isFinite(jobId) || !Number.isFinite(concursoId)) return null;
  return {
    id: Number.isFinite(Number(raw?.id)) ? Number(raw.id) : undefined,
    job_id: jobId,
    concurso_id: concursoId,
    status: normalizeStatus(raw?.status ?? raw?.estado),
    stage: raw?.stage ?? null,
    progress: raw?.progress ?? raw?.progresso ?? null,
    analysis_id: raw?.analysis_id ?? raw?.analise_id ?? raw?.id ?? null,
    error: raw?.error ?? raw?.erro ?? null,
    updated_at: raw?.updated_at ?? null,
  };
}

export function analysisStatusLabel(job?: AnalysisJobState | null): string {
  if (!job) return "Em processamento";
  if (job.status === "completed" || job.status === "partial") return "Ver análise AI";
  if (job.status === "failed" || job.status === "cancelled" || job.status === "interrupted") {
    return "Tentar novamente";
  }
  const stage = job.stage || "";
  if (stage === "locating_documents") return "A procurar documentos";
  if (stage === "downloading_documents") return "A transferir documentos";
  if (stage === "extracting_documents") return "A analisar as peças";
  if (stage === "generating_competition_analysis") return "A criar análise";
  if (stage === "matching_company_profile") return "A cruzar com o perfil da empresa";
  if (job.status === "queued") return "A preparar análise";
  return "Em processamento";
}

export async function fetchAnalysisJobState(
  token: string,
  jobId: number,
): Promise<AnalysisJobState> {
  const response = await fetch(`${API_URL}/analises/jobs/${jobId}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Erro ao consultar estado da análise (${response.status})`);
  }
  const normalized = normalizeAnalysisJob(await response.json());
  if (!normalized) throw new Error("Resposta inválida do estado da análise.");
  return normalized;
}
