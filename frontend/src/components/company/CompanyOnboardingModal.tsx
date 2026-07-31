"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, Check, Loader2, X } from "lucide-react";
import { API_URL } from "@/lib/api";
import CompanySourceStep from "./CompanySourceStep";
import CompanyInterviewStep from "./CompanyInterviewStep";
import CompanyProfileSummary from "./CompanyProfileSummary";
import { saveCompanyProfileWithDiagnostics } from "@/lib/company-profile-api";
import {
  CompanyBasicInfo,
  CompanyCreationChoice,
  CompanyInterviewAnswerValue,
  CompanyInterviewQuestion,
  CompanyProfile,
  CompanyProfilePath,
  CompanySearchResult,
  CompanySourceSummary,
  CompanySourceStatus,
  CompanyWebsiteIngestionResult,
  createEmptyCompanyProfile,
  normalizeCompanyProfile,
} from "./company-types";
import {
  buildCompanyOnboardingDraftKey,
  clearCompanyOnboardingDraft,
  createInitialSourceStatuses,
  loadCompanyOnboardingDraft,
  restoreSourceStatusDetails,
  saveCompanyOnboardingDraft,
  toFileMeta,
  type CompanyOnboardingFileMeta,
} from "./company-onboarding-draft";

type Props = {
  open: boolean;
  token: string;
  userId: string | null;
  company: CompanyBasicInfo | null;
  profile: CompanyProfile;
  hasProfile: boolean;
  onCompanyUpdated: (company: CompanyBasicInfo | null) => void;
  onProfileUpdated: (profile: CompanyProfile) => void;
  onComplete: (profile: CompanyProfile, company: CompanyBasicInfo | null) => void;
  onClose: () => void;
};

type SourceTaskResult = {
  key: "website" | "portfolio" | "institutional";
  ok: boolean;
  detail: string;
  status?: CompanySourceStatus["status"];
  factsCreated?: number;
  projectsFound?: string[];
  pagesVisited?: number;
  servicesFound?: string[];
  competencesFound?: string[];
  warnings?: string[];
  origin?: string;
};

function updateSourceStatuses(
  statuses: CompanySourceStatus[],
  key: SourceTaskResult["key"],
  patch: Partial<CompanySourceStatus>,
) {
  return statuses.map((status) =>
    status.key === key ? { ...status, ...patch } : status,
  );
}

function statusFromWebsiteResult(
  result: CompanyWebsiteIngestionResult,
): CompanySourceStatus["status"] {
  if (result.status === "failed") return "error";
  if ((result.facts_created ?? 0) <= 0) return "no_results";
  if (result.status === "partial" || (result.warnings ?? []).length > 0) {
    return "partial";
  }
  return "processed";
}

function detailFromCounts(facts = 0, projects = 0): string {
  if (facts <= 0 && projects <= 0) return "Sem factos úteis encontrados.";
  const factLabel = facts === 1 ? "1 facto" : `${facts} factos`;
  const projectLabel = projects === 1 ? "1 projeto" : `${projects} projetos`;
  return `${factLabel}; ${projectLabel}.`;
}

function mergePersistedSourcesIntoStatuses(
  statuses: CompanySourceStatus[],
  sources: CompanySourceSummary[],
): CompanySourceStatus[] {
  let next: CompanySourceStatus[] = statuses.length
    ? statuses
    : [
        { key: "website", label: "Website", status: "not_added" },
        { key: "portfolio", label: "Portfolio", status: "not_added" },
        {
          key: "institutional",
          label: "Documentos institucionais",
          status: "not_added",
        },
      ];

  for (const source of sources) {
    const key =
      source.source_type === "website"
        ? "website"
        : source.source_type === "portfolio"
          ? "portfolio"
          : "institutional";
    next = updateSourceStatuses(next, key, {
      status: source.status,
      name: source.name,
      origin: source.source,
      submitted_at: source.submitted_at ?? undefined,
      facts_created: source.facts_count,
      projects_found: source.projects_count,
      services_found: source.services_found ?? [],
      competences_found: source.competences_found ?? [],
      warnings: source.warnings ?? [],
      detail: detailFromCounts(source.facts_count, source.projects_count),
    });
  }

  return next;
}

async function safeReadJson(response: Response): Promise<unknown> {
  const text = await response.text();
  const trimmed = text.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

async function saveCompanyProfile(
  token: string,
  profile: CompanyProfile,
  hasProfile: boolean,
): Promise<CompanyProfile> {
  return saveCompanyProfileWithDiagnostics(token, profile, hasProfile);
}

async function createCompany(
  token: string,
  name: string,
  website: string,
): Promise<CompanyBasicInfo> {
  const response = await fetch(`${API_URL}/company`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      name: name.trim(),
      ...(website.trim() ? { website: website.trim() } : {}),
    }),
  });

  if (!response.ok) {
    const data = await safeReadJson(response);
    throw new Error(
      (data as { detail?: string } | null)?.detail ||
        "Não foi possível criar a empresa.",
    );
  }

  const data = (await safeReadJson(response)) as Partial<CompanyBasicInfo> | null;
  return {
    id: typeof data?.id === "number" ? data.id : null,
    name: String(data?.name ?? name),
    website: String(data?.website ?? website),
    owner_user_id: data?.owner_user_id,
  };
}

async function fetchCompanyProfile(
  token: string,
): Promise<{ profile: CompanyProfile; hasProfile: boolean }> {
  const response = await fetch(`${API_URL}/company/profile`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (response.status === 404) {
    return { profile: createEmptyCompanyProfile(), hasProfile: false };
  }

  if (!response.ok) {
    throw new Error("Não foi possível carregar o perfil da empresa.");
  }

  return {
    profile: normalizeCompanyProfile(await safeReadJson(response)),
    hasProfile: true,
  };
}

async function fetchCompanySources(token: string): Promise<CompanySourceSummary[]> {
  const response = await fetch(`${API_URL}/company/sources`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (response.status === 404) return [];
  if (!response.ok) {
    throw new Error("NÃ£o foi possÃ­vel carregar as fontes da empresa.");
  }

  const data = (await safeReadJson(response)) as { sources?: unknown } | null;
  return Array.isArray(data?.sources)
    ? (data.sources as CompanySourceSummary[])
    : [];
}

async function deleteCompanySource(
  token: string,
  sourceType: string,
  source: string,
): Promise<CompanySourceSummary[]> {
  const response = await fetch(`${API_URL}/company/sources`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ source_type: sourceType, source }),
  });

  if (!response.ok) {
    const data = await safeReadJson(response);
    throw new Error(
      (data as { detail?: string } | null)?.detail ||
        "NÃ£o foi possÃ­vel remover a fonte.",
    );
  }

  const data = (await safeReadJson(response)) as { sources?: unknown } | null;
  return Array.isArray(data?.sources)
    ? (data.sources as CompanySourceSummary[])
    : [];
}

async function loadInterview(token: string): Promise<{
  session_id: number | null;
  questions: CompanyInterviewQuestion[];
}> {
  const response = await fetch(`${API_URL}/company/interview`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    const data = await safeReadJson(response);
    throw new Error(
      (data as { detail?: string } | null)?.detail ||
        "Não foi possível carregar a entrevista AI.",
    );
  }

  const data = (await safeReadJson(response)) as {
    session_id?: unknown;
    questions?: unknown;
  } | null;

  return {
    session_id: typeof data?.session_id === "number" ? data.session_id : null,
    questions: Array.isArray(data?.questions)
      ? (data.questions as CompanyInterviewQuestion[])
      : [],
  };
}

async function saveInterviewAnswer(
  token: string,
  question: CompanyInterviewQuestion,
  answer: CompanyInterviewAnswerValue,
): Promise<void> {
  const response = await fetch(
    `${API_URL}/company/interview/${question.id}/answer`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ answer }),
    },
  );

  if (!response.ok) {
    const data = await safeReadJson(response);
    throw new Error(
      (data as { detail?: string } | null)?.detail ||
        "Não foi possível guardar a resposta.",
    );
  }

  if (question.question_source !== "validation") {
    const applyResponse = await fetch(
      `${API_URL}/company/interview/${question.id}/apply`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      },
    );

    if (!applyResponse.ok) {
      const data = await safeReadJson(applyResponse);
      throw new Error(
        (data as { detail?: string } | null)?.detail ||
          "Não foi possível aplicar a resposta ao perfil.",
      );
    }
  }
}

async function fileToBase64(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";

  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }

  return window.btoa(binary);
}

async function ingestFile(
  token: string,
  file: File,
  sourceType: "portfolio" | "institutional",
): Promise<{
  facts_created?: number;
  projects_found?: string[];
}> {
  const response = await fetch(`${API_URL}/company/documents/ingest-file`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      filename: file.name,
      content_base64: await fileToBase64(file),
      source_type: sourceType,
    }),
  });

  if (!response.ok) {
    const data = await safeReadJson(response);
    throw new Error(
      (data as { detail?: string } | null)?.detail ||
        `Não foi possível processar ${file.name}.`,
    );
  }

  const data = (await safeReadJson(response)) as {
    facts_created?: unknown;
    extraction?: { facts?: Array<{ field?: string; value?: unknown }> };
  } | null;
  const projectFact = data?.extraction?.facts?.find(
    (fact) => fact.field === "projects.items",
  );

  return {
    facts_created:
      typeof data?.facts_created === "number" ? data.facts_created : undefined,
    projects_found: Array.isArray(projectFact?.value)
      ? (projectFact.value as string[])
      : [],
  };
}

async function ingestWebsite(
  token: string,
  url: string,
): Promise<CompanyWebsiteIngestionResult> {
  const response = await fetch(`${API_URL}/company/website/ingest`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    const data = await safeReadJson(response);
    throw new Error(
      (data as { detail?: string } | null)?.detail ||
        "Não foi possível processar o website.",
    );
  }

  return (await safeReadJson(response)) as CompanyWebsiteIngestionResult;
}

async function searchCompanies(
  token: string,
  query: string,
  website: string,
): Promise<CompanySearchResult[]> {
  const params = new URLSearchParams();
  if (query.trim()) params.set("query", query.trim());
  if (website.trim()) params.set("website", website.trim());

  const response = await fetch(`${API_URL}/company/search?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    const data = await safeReadJson(response);
    throw new Error(
      (data as { detail?: string } | null)?.detail ||
        "Não foi possível pesquisar empresas existentes.",
    );
  }

  const data = (await safeReadJson(response)) as { results?: unknown } | null;
  return Array.isArray(data?.results)
    ? (data.results as CompanySearchResult[])
    : [];
}

export default function CompanyOnboardingModal({
  open,
  token,
  userId,
  company,
  profile,
  hasProfile,
  onCompanyUpdated,
  onProfileUpdated,
  onComplete,
  onClose,
}: Props) {
  const draftKey = buildCompanyOnboardingDraftKey(userId);
  const initialName = profile.identity.company_name || company?.name || "";
  const initialWebsite = profile.identity.website || company?.website || "";

  const [step, setStep] = useState(0);
  const [companyName, setCompanyName] = useState(initialName);
  const [website, setWebsite] = useState(initialWebsite);
  const [companyChoice, setCompanyChoice] =
    useState<CompanyCreationChoice>(company ? "new" : null);
  const [profilePath, setProfilePath] = useState<CompanyProfilePath>(null);
  const [portfolioFiles, setPortfolioFiles] = useState<File[]>([]);
  const [institutionalFiles, setInstitutionalFiles] = useState<File[]>([]);
  const [portfolioFileMeta, setPortfolioFileMeta] = useState<
    CompanyOnboardingFileMeta[]
  >([]);
  const [institutionalFileMeta, setInstitutionalFileMeta] = useState<
    CompanyOnboardingFileMeta[]
  >([]);
  const [sourceStatuses, setSourceStatuses] = useState<CompanySourceStatus[]>(
    [],
  );
  const [sourceSummaries, setSourceSummaries] = useState<CompanySourceSummary[]>(
    [],
  );
  const [workingCompany, setWorkingCompany] =
    useState<CompanyBasicInfo | null>(company);
  const [workingHasProfile, setWorkingHasProfile] = useState(hasProfile);
  const [processing, setProcessing] = useState(false);
  const [loadingInterview, setLoadingInterview] = useState(false);
  const [savingAnswerId, setSavingAnswerId] = useState<number | null>(null);
  const [savingFinal, setSavingFinal] = useState(false);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [questions, setQuestions] = useState<CompanyInterviewQuestion[]>([]);
  const [answers, setAnswers] = useState<
    Record<number, CompanyInterviewAnswerValue>
  >({});
  const [summaryProfile, setSummaryProfile] = useState<CompanyProfile>(profile);
  const [error, setError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<CompanySearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [selectedExistingCompanyId, setSelectedExistingCompanyId] =
    useState<number | null>(null);
  const [draftReady, setDraftReady] = useState(false);
  const wasOpenRef = useRef(false);

  const hasExistingCompany = Boolean(workingCompany?.id);
  const importSourcesCount =
    (website.trim() ? 1 : 0) + portfolioFiles.length + institutionalFiles.length;

  const canStart = useMemo(() => {
    if (!token || processing || loadingInterview || savingFinal) return false;
    if (!hasExistingCompany && companyChoice !== "new") return false;
    if (!companyName.trim()) return false;
    if (profilePath === "manual") return true;
    if (profilePath === "import") return importSourcesCount > 0;
    return false;
  }, [
    companyChoice,
    companyName,
    hasExistingCompany,
    importSourcesCount,
    loadingInterview,
    processing,
    profilePath,
    savingFinal,
    token,
  ]);

  useEffect(() => {
    if (!open) {
      wasOpenRef.current = false;
      return;
    }
    if (wasOpenRef.current) return;
    wasOpenRef.current = true;

    const draft = loadCompanyOnboardingDraft(draftKey);
    if (draft) {
      setStep(draft.step);
      setCompanyName(draft.companyName);
      setWebsite(draft.website);
      setCompanyChoice(draft.companyChoice);
      setProfilePath(draft.profilePath);
      setPortfolioFiles([]);
      setInstitutionalFiles([]);
      setPortfolioFileMeta(draft.portfolioFileMeta ?? []);
      setInstitutionalFileMeta(draft.institutionalFileMeta ?? []);
      setSourceStatuses(
        restoreSourceStatusDetails(
          draft.sourceStatuses ?? [],
          draft.portfolioFileMeta ?? [],
          draft.institutionalFileMeta ?? [],
        ),
      );
      setSourceSummaries([]);
      setWorkingCompany(draft.workingCompany ?? company);
      setWorkingHasProfile(draft.workingHasProfile ?? hasProfile);
      setProcessing(false);
      setLoadingInterview(false);
      setSavingAnswerId(null);
      setSavingFinal(false);
      setSessionId(draft.sessionId ?? null);
      setQuestions(draft.questions ?? []);
      setAnswers(draft.answers ?? {});
      setSummaryProfile(draft.summaryProfile ?? profile);
      setError(null);
      setSearchResults([]);
      setSearchLoading(false);
      setSearchError(null);
      setSelectedExistingCompanyId(draft.selectedExistingCompanyId ?? null);
      setDraftReady(true);
      return;
    }

    const nextName = profile.identity.company_name || company?.name || "";
    const nextWebsite = profile.identity.website || company?.website || "";
    setStep(0);
    setCompanyName(nextName);
    setWebsite(nextWebsite);
    setCompanyChoice(company ? "new" : null);
    setProfilePath(null);
    setPortfolioFiles([]);
    setInstitutionalFiles([]);
    setPortfolioFileMeta([]);
    setInstitutionalFileMeta([]);
    setSourceStatuses([]);
    setSourceSummaries([]);
    setWorkingCompany(company);
    setWorkingHasProfile(hasProfile);
    setProcessing(false);
    setLoadingInterview(false);
    setSavingAnswerId(null);
    setSavingFinal(false);
    setSessionId(null);
    setQuestions([]);
    setAnswers({});
    setSummaryProfile(profile);
    setError(null);
    setSearchResults([]);
    setSearchLoading(false);
    setSearchError(null);
    setSelectedExistingCompanyId(null);
    setDraftReady(true);
  }, [company, draftKey, hasProfile, open, profile]);

  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };

    window.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [onClose, open]);

  useEffect(() => {
    if (!open) return;

    setSourceStatuses((current) => {
      const base =
        current.length > 0
          ? current
          : createInitialSourceStatuses(
              website,
              portfolioFileMeta,
              institutionalFileMeta,
            );

      return base.map((status) => {
        if (status.key === "website") {
          return {
            ...status,
            status: website.trim() ? status.status : "not_added",
            detail: website.trim() ? status.detail : undefined,
          };
        }
        if (status.key === "portfolio") {
          return {
            ...status,
            status: portfolioFiles.length ? status.status : "not_added",
            detail: portfolioFiles.length
              ? status.detail
              : portfolioFileMeta.length
                ? "É necessário voltar a selecionar este ficheiro."
                : undefined,
          };
        }
        return {
          ...status,
          status: institutionalFiles.length ? status.status : "not_added",
          detail: institutionalFiles.length
            ? status.detail
            : institutionalFileMeta.length
              ? "É necessário voltar a selecionar este ficheiro."
              : undefined,
        };
      });
    });
  }, [
    institutionalFileMeta,
    institutionalFiles.length,
    open,
    portfolioFileMeta,
    portfolioFiles.length,
    website,
  ]);

  useEffect(() => {
    if (!open || !draftReady || !draftKey) return;

    saveCompanyOnboardingDraft(draftKey, {
      version: 1,
      updatedAt: new Date().toISOString(),
      step,
      companyName,
      website,
      companyChoice,
      profilePath,
      selectedExistingCompanyId,
      workingCompany,
      workingHasProfile,
      sourceStatuses,
      portfolioFileMeta,
      institutionalFileMeta,
      sessionId,
      questions,
      answers,
      summaryProfile,
    });
  }, [
    answers,
    companyChoice,
    companyName,
    draftKey,
    draftReady,
    institutionalFileMeta,
    open,
    portfolioFileMeta,
    profilePath,
    questions,
    selectedExistingCompanyId,
    sessionId,
    sourceStatuses,
    step,
    summaryProfile,
    website,
    workingCompany,
    workingHasProfile,
  ]);

  useEffect(() => {
    if (!open || !draftReady || !token) return;

    let active = true;
    fetchCompanySources(token)
      .then((sources) => {
        if (!active) return;
        setSourceSummaries(sources);
        setSourceStatuses((current) =>
          mergePersistedSourcesIntoStatuses(current, sources),
        );
      })
      .catch(() => {
        if (!active) return;
        setSourceSummaries([]);
      });

    return () => {
      active = false;
    };
  }, [draftReady, open, token]);

  if (!open) return null;

  function profileWithIdentity(base: CompanyProfile): CompanyProfile {
    return {
      ...base,
      identity: {
        ...base.identity,
        company_name: companyName.trim(),
        website: website.trim(),
      },
    };
  }

  async function ensureCompany(): Promise<CompanyBasicInfo> {
    if (workingCompany?.id) return workingCompany;

    if (companyChoice === "existing") {
      throw new Error(
        "A empresa existente precisa de convite ou aprovação antes de poder ser usada.",
      );
    }

    if (companyChoice !== "new") {
      throw new Error("Escolha se pretende criar uma empresa nova ou procurar uma existente.");
    }

    const created = await createCompany(token, companyName, website);
    setWorkingCompany(created);
    onCompanyUpdated(created);
    return created;
  }

  async function refreshProfileAfterWork() {
    const [latest, sources] = await Promise.all([
      fetchCompanyProfile(token),
      fetchCompanySources(token),
    ]);
    const normalized = profileWithIdentity(latest.profile);
    setWorkingHasProfile(latest.hasProfile);
    setSummaryProfile(normalized);
    onProfileUpdated(normalized);
    setSourceSummaries(sources);
    setSourceStatuses((current) =>
      mergePersistedSourcesIntoStatuses(current, sources),
    );
    return { profile: normalized, hasProfile: latest.hasProfile };
  }

  async function refreshInterviewAfterSourceChange() {
    const interview = await loadInterview(token);
    setSessionId(interview.session_id);
    setQuestions(interview.questions);
  }

  async function handleSearchCompanies() {
    try {
      setSearchLoading(true);
      setSearchError(null);
      setSelectedExistingCompanyId(null);
      setSearchResults(await searchCompanies(token, companyName, website));
    } catch (searchProblem) {
      setSearchError(
        searchProblem instanceof Error
          ? searchProblem.message
          : "Não foi possível pesquisar empresas.",
      );
    } finally {
      setSearchLoading(false);
    }
  }

  function handlePortfolioFilesChange(nextFiles: File[]) {
    setPortfolioFiles(nextFiles);
    setPortfolioFileMeta(nextFiles.map(toFileMeta));
    setSourceStatuses((current) =>
      current.map((status) =>
        status.key === "portfolio"
          ? { ...status, detail: undefined }
          : status,
      ),
    );
  }

  function handleInstitutionalFilesChange(nextFiles: File[]) {
    setInstitutionalFiles(nextFiles);
    setInstitutionalFileMeta(nextFiles.map(toFileMeta));
    setSourceStatuses((current) =>
      current.map((status) =>
        status.key === "institutional"
          ? { ...status, detail: undefined }
          : status,
      ),
    );
  }

  function persistedSourceForKey(key: SourceTaskResult["key"]) {
    const sourceType =
      key === "website" ? "website" : key === "portfolio" ? "portfolio" : "document";
    return sourceSummaries.find((source) => source.source_type === sourceType);
  }

  async function reconcileAfterSourceMutation() {
    await refreshProfileAfterWork();
    await refreshInterviewAfterSourceChange();
  }

  async function handleRemoveSource(key: SourceTaskResult["key"]) {
    const source = persistedSourceForKey(key);
    const confirmed = window.confirm(
      "Esta acao ira remover esta fonte e atualizar automaticamente o perfil da empresa. Pretende continuar?",
    );
    if (!confirmed) return;

    try {
      setError(null);
      setSourceStatuses((current) =>
        updateSourceStatuses(current, key, {
          status: "processing",
          detail: "A remover fonte...",
        }),
      );

      if (source) {
        await deleteCompanySource(token, source.source_type, source.source);
      }

      if (key === "website") {
        setWebsite("");
      } else if (key === "portfolio") {
        setPortfolioFiles([]);
        setPortfolioFileMeta([]);
      } else {
        setInstitutionalFiles([]);
        setInstitutionalFileMeta([]);
      }

      await reconcileAfterSourceMutation();
      setSourceStatuses((current) =>
        updateSourceStatuses(current, key, {
          status: "not_added",
          detail: undefined,
          origin: undefined,
          name: undefined,
          facts_created: undefined,
          projects_found: undefined,
          pages_visited: undefined,
          services_found: [],
          competences_found: [],
          warnings: [],
        }),
      );
    } catch (removeError) {
      setSourceStatuses((current) =>
        updateSourceStatuses(current, key, {
          status: "error",
          detail:
            removeError instanceof Error
              ? removeError.message
              : "Nao foi possivel remover a fonte.",
        }),
      );
      setError(
        removeError instanceof Error
          ? removeError.message
          : "Nao foi possivel remover a fonte.",
      );
    }
  }

  async function handleReprocessSource(key: SourceTaskResult["key"]) {
    try {
      setError(null);
      setSourceStatuses((current) =>
        updateSourceStatuses(current, key, {
          status: "processing",
          detail: "A reprocessar fonte...",
        }),
      );

      const source = persistedSourceForKey(key);
      if (source) {
        await deleteCompanySource(token, source.source_type, source.source);
      }

      if (key === "website") {
        if (!website.trim() && !source?.name) {
          throw new Error("Introduza um website antes de reprocessar.");
        }
        const result = await ingestWebsite(token, website.trim() || source?.name || "");
        setSourceStatuses((current) =>
          updateSourceStatuses(current, "website", {
            status: statusFromWebsiteResult(result),
            detail: detailFromCounts(
              result.facts_created ?? 0,
              result.projects_found?.length ?? 0,
            ),
            facts_created: result.facts_created ?? 0,
            projects_found: result.projects_found?.length ?? 0,
            pages_visited: result.pages_visited ?? 0,
            services_found: result.services_found ?? [],
            competences_found: result.competences_found ?? [],
            warnings: result.warnings ?? [],
            origin: result.source_url || website,
          }),
        );
      } else {
        const files = key === "portfolio" ? portfolioFiles : institutionalFiles;
        const sourceType = key === "portfolio" ? "portfolio" : "institutional";
        if (files.length === 0) {
          throw new Error("Selecione novamente o ficheiro para reprocessar.");
        }
        let facts = 0;
        let projects = 0;
        for (const file of files) {
          const result = await ingestFile(token, file, sourceType);
          facts += result.facts_created ?? 0;
          projects += result.projects_found?.length ?? 0;
        }
        setSourceStatuses((current) =>
          updateSourceStatuses(current, key, {
            status: facts > 0 ? "processed" : "no_results",
            detail: detailFromCounts(facts, projects),
            facts_created: facts,
            projects_found: projects,
          }),
        );
      }

      await reconcileAfterSourceMutation();
    } catch (reprocessError) {
      setSourceStatuses((current) =>
        updateSourceStatuses(current, key, {
          status: "error",
          detail:
            reprocessError instanceof Error
              ? reprocessError.message
              : "Nao foi possivel reprocessar a fonte.",
        }),
      );
      setError(
        reprocessError instanceof Error
          ? reprocessError.message
          : "Nao foi possivel reprocessar a fonte.",
      );
    }
  }

  async function prepareInterview() {
    setLoadingInterview(true);
    const interview = await loadInterview(token);
    setSessionId(interview.session_id);
    setQuestions(interview.questions);
    setLoadingInterview(false);
    setStep(2);
  }

  async function handleStart() {
    try {
      setError(null);
      await ensureCompany();

      const baseProfile = profileWithIdentity(summaryProfile);
      setSummaryProfile(baseProfile);
      onProfileUpdated(baseProfile);

      if (profilePath === "manual") {
        await prepareInterview();
        return;
      }

      if (profilePath !== "import" || importSourcesCount === 0) {
        throw new Error("Adicione pelo menos uma fonte ou escolha criar manualmente.");
      }

      setProcessing(true);
      setStep(1);

      const tasks: Array<Promise<SourceTaskResult>> = [];
      const activeKeys = new Set<SourceTaskResult["key"]>();

      if (website.trim()) {
        activeKeys.add("website");
        tasks.push(
          ingestWebsite(token, website).then(
            (result) => ({
              key: "website",
              ok: result.status !== "failed",
              detail: detailFromCounts(
                result.facts_created ?? 0,
                result.projects_found?.length ?? 0,
              ),
              status: statusFromWebsiteResult(result),
              factsCreated: result.facts_created ?? 0,
              projectsFound: result.projects_found ?? [],
              pagesVisited: result.pages_visited ?? 0,
              servicesFound: result.services_found ?? [],
              competencesFound: result.competences_found ?? [],
              warnings: result.warnings ?? [],
              origin: result.source_url || website,
            }),
            (problem) => ({
              key: "website",
              ok: false,
              detail:
                problem instanceof Error
                  ? problem.message
                  : "Erro ao processar website.",
            }),
          ),
        );
      }

      for (const file of portfolioFiles) {
        activeKeys.add("portfolio");
        tasks.push(
          ingestFile(token, file, "portfolio").then(
            (result) => ({
              key: "portfolio",
              ok: (result.facts_created ?? 0) > 0,
              detail: `${file.name} - ${detailFromCounts(
                result.facts_created ?? 0,
                result.projects_found?.length ?? 0,
              )}`,
              status:
                (result.facts_created ?? 0) > 0 ? "processed" : "no_results",
              factsCreated: result.facts_created ?? 0,
              projectsFound: result.projects_found ?? [],
              origin: `portfolio:${file.name}`,
            }),
            (problem) => ({
              key: "portfolio",
              ok: false,
              detail:
                problem instanceof Error
                  ? `${file.name}: ${problem.message}`
                  : `${file.name}: erro ao processar.`,
            }),
          ),
        );
      }

      for (const file of institutionalFiles) {
        activeKeys.add("institutional");
        tasks.push(
          ingestFile(token, file, "institutional").then(
            (result) => ({
              key: "institutional",
              ok: (result.facts_created ?? 0) > 0,
              detail: `${file.name} - ${detailFromCounts(
                result.facts_created ?? 0,
                result.projects_found?.length ?? 0,
              )}`,
              status:
                (result.facts_created ?? 0) > 0 ? "processed" : "no_results",
              factsCreated: result.facts_created ?? 0,
              projectsFound: result.projects_found ?? [],
              origin: `institutional:${file.name}`,
            }),
            (problem) => ({
              key: "institutional",
              ok: false,
              detail:
                problem instanceof Error
                  ? `${file.name}: ${problem.message}`
                  : `${file.name}: erro ao processar.`,
            }),
          ),
        );
      }

      setSourceStatuses((current) =>
        current.map((status) =>
          activeKeys.has(status.key as SourceTaskResult["key"])
            ? { ...status, status: "processing", detail: undefined }
            : status,
        ),
      );

      const settled = await Promise.allSettled(tasks);
      const results = settled.map((item) =>
        item.status === "fulfilled"
          ? item.value
          : ({
              key: "institutional",
              ok: false,
              detail: "Erro inesperado ao processar fonte.",
            } as SourceTaskResult),
      );

      const successful = results.filter((item) => item.ok);
      setSourceStatuses((current) => {
        let next = current;
        for (const key of ["website", "portfolio", "institutional"] as const) {
          const keyResults = results.filter((item) => item.key === key);
          if (keyResults.length === 0) {
            continue;
          }
          const ok = keyResults.some((item) => item.ok);
          const detail = ok
            ? keyResults
                .filter((item) => item.ok)
                .map((item) => item.detail)
                .slice(0, 3)
                .join(", ")
            : keyResults[0]?.detail;
          next = updateSourceStatuses(next, key, {
            status: ok ? keyResults.find((item) => item.ok)?.status ?? "processed" : "error",
            detail,
            facts_created: keyResults.reduce(
              (total, item) => total + (item.factsCreated ?? 0),
              0,
            ),
            projects_found: keyResults.reduce(
              (total, item) => total + (item.projectsFound?.length ?? 0),
              0,
            ),
            pages_visited: keyResults.find((item) => item.pagesVisited !== undefined)
              ?.pagesVisited,
            services_found: keyResults.flatMap((item) => item.servicesFound ?? []),
            competences_found: keyResults.flatMap(
              (item) => item.competencesFound ?? [],
            ),
            warnings: keyResults.flatMap((item) => item.warnings ?? []),
            origin: keyResults.find((item) => item.origin)?.origin,
          });
        }
        return next;
      });

      setProcessing(false);

      if (successful.length === 0) {
        setStep(0);
        throw new Error(
          "Nenhuma fonte foi processada com sucesso. Pode corrigir as fontes ou avançar pelo caminho manual.",
        );
      }

      await refreshProfileAfterWork();
      await prepareInterview();
    } catch (startProblem) {
      setProcessing(false);
      setLoadingInterview(false);
      setError(
        startProblem instanceof Error
          ? startProblem.message
          : "Não foi possível preparar o onboarding.",
      );
    }
  }

  async function handleSubmitAnswer(
    question: CompanyInterviewQuestion,
    answerOverride?: CompanyInterviewAnswerValue,
  ) {
    const rawAnswer =
      answerOverride !== undefined ? answerOverride : answers[question.id];
    const hasAnswer =
      rawAnswer !== null &&
      rawAnswer !== undefined &&
      (typeof rawAnswer !== "string" || rawAnswer.trim().length > 0) &&
      (!(Array.isArray(rawAnswer)) || rawAnswer.length > 0);
    if (!hasAnswer) return;

    try {
      setSavingAnswerId(question.id);
      setError(null);
      await saveInterviewAnswer(token, question, rawAnswer);
      await refreshProfileAfterWork();
      const interview = await loadInterview(token);
      setSessionId(interview.session_id);
      setQuestions(interview.questions);
      setAnswers((current) => {
        const next = { ...current };
        delete next[question.id];
        return next;
      });
    } catch (answerError) {
      setError(
        answerError instanceof Error
          ? answerError.message
          : "Não foi possível guardar a resposta.",
      );
    } finally {
      setSavingAnswerId(null);
    }
  }

  async function handleGoToSummary() {
    try {
      setLoadingInterview(true);
      setError(null);
      await refreshProfileAfterWork();
      setStep(3);
    } catch (summaryError) {
      setError(
        summaryError instanceof Error
          ? summaryError.message
          : "Não foi possível carregar o resumo final.",
      );
    } finally {
      setLoadingInterview(false);
    }
  }

  async function finishOnboarding() {
    try {
      setSavingFinal(true);
      setError(null);
      const finalCompany = await ensureCompany();
      const finalProfile = profileWithIdentity(summaryProfile);
      const saved = await saveCompanyProfile(
        token,
        finalProfile,
        workingHasProfile,
      );
      const normalized = normalizeCompanyProfile(saved);
      setWorkingHasProfile(true);
      setSummaryProfile(normalized);
      onProfileUpdated(normalized);
      clearCompanyOnboardingDraft(draftKey);
      setDraftReady(false);
      onComplete(normalized, finalCompany);
    } catch (finishProblem) {
      setError(
        finishProblem instanceof Error
          ? finishProblem.message
          : "Não foi possível guardar o perfil da empresa.",
      );
    } finally {
      setSavingFinal(false);
    }
  }

  const dots = ["fontes", "processamento", "entrevista", "perfil"];

  return (
    <div className="onboarding-overlay" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <div className="onboarding-modal">
        <button className="onboarding-close" onClick={onClose} type="button">
          <X size={20} />
        </button>

        <div className="onboarding-progress">
          {dots.map((_, index) => (
            <div
              key={index}
              className={`onboarding-dot ${index <= step ? "active" : ""}`}
            />
          ))}
        </div>

        {step === 0 && (
          <CompanySourceStep
            companyName={companyName}
            website={website}
            companyChoice={companyChoice}
            profilePath={profilePath}
            portfolioFiles={portfolioFiles}
            institutionalFiles={institutionalFiles}
            portfolioFileMeta={portfolioFileMeta}
            institutionalFileMeta={institutionalFileMeta}
            searchResults={searchResults}
            searchLoading={searchLoading}
            searchError={searchError}
            selectedExistingCompanyId={selectedExistingCompanyId}
            sourceStatuses={sourceStatuses}
            hasExistingCompany={hasExistingCompany}
            onCompanyNameChange={setCompanyName}
            onWebsiteChange={setWebsite}
            onCompanyChoiceChange={(choice) => {
              setCompanyChoice(choice);
              setSelectedExistingCompanyId(null);
              setError(null);
            }}
            onProfilePathChange={setProfilePath}
            onPortfolioFilesChange={handlePortfolioFilesChange}
            onInstitutionalFilesChange={handleInstitutionalFilesChange}
            onSearchCompanies={handleSearchCompanies}
            onSelectExistingCompany={setSelectedExistingCompanyId}
            onRemoveSource={handleRemoveSource}
            onReprocessSource={handleReprocessSource}
          />
        )}

        {step === 1 && (
          <div className="onboarding-step">
            <h2>Processamento AI</h2>
            <p>A analisar a informação da empresa...</p>
            <div
              style={{
                display: "grid",
                gap: "12px",
                padding: "18px",
                borderRadius: "16px",
                background: "#fafaf7",
                border: "1px solid #ecece5",
                color: "#666",
              }}
            >
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Loader2 size={18} className="spin" />
                A extrair texto real do website e dos documentos enviados.
              </div>
              <ul style={{ margin: 0, paddingLeft: "18px" }}>
                {sourceStatuses.map((status) => (
                  <li key={status.key}>
                    {status.label}: {status.status}
                    {status.detail ? ` — ${status.detail}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {step === 2 && (
          <CompanyInterviewStep
            sessionId={sessionId}
            questions={questions}
            answers={answers}
            submittingQuestionId={savingAnswerId}
            loading={loadingInterview}
            onAnswerChange={(questionId, value) =>
              setAnswers((current) => ({
                ...current,
                [questionId]: value,
              }))
            }
            onSubmitAnswer={handleSubmitAnswer}
          />
        )}

        {step === 3 && (
          <CompanyProfileSummary
            profile={summaryProfile}
            companyName={companyName}
            sourceStatuses={sourceStatuses}
          />
        )}

        {error && (
          <div
            style={{
              padding: "14px 16px",
              borderRadius: "14px",
              background: "#fff5f5",
              border: "1px solid #f0cccc",
              color: "#9f3a3a",
              marginTop: "18px",
            }}
            role="alert"
          >
            {error}
          </div>
        )}

        <div className="onboarding-actions">
          {step > 0 && (
            <button
              className="onboarding-btn secondary"
              onClick={() => setStep((current) => Math.max(0, current - 1))}
              disabled={processing || loadingInterview || savingAnswerId !== null}
              type="button"
            >
              Anterior
            </button>
          )}

          {step === 0 && (
            <button
              className="onboarding-btn primary"
              onClick={handleStart}
              disabled={!canStart}
              type="button"
            >
              {processing || loadingInterview ? (
                <>
                  <Loader2 size={18} className="spin" />
                  A preparar...
                </>
              ) : (
                <>
                  {profilePath === "manual" ? "Começar entrevista" : "Importar e continuar"}
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          )}

          {step === 2 && (
            <button
              className="onboarding-btn primary"
              onClick={handleGoToSummary}
              disabled={loadingInterview}
              type="button"
            >
              <Check size={18} />
              Ver resumo
            </button>
          )}

          {step === 3 && (
            <button
              className="onboarding-btn primary"
              onClick={finishOnboarding}
              disabled={savingFinal}
              type="button"
            >
              {savingFinal ? (
                <>
                  <Loader2 size={18} className="spin" />
                  A guardar...
                </>
              ) : (
                <>
                  <Check size={18} />
                  Guardar perfil da empresa
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
