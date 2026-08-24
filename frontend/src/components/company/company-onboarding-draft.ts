import type {
  CompanyBasicInfo,
  CompanyCreationChoice,
  CompanyInterviewAnswerValue,
  CompanyInterviewQuestion,
  CompanyProfile,
  CompanyProfilePath,
  CompanySourceStatus,
} from "./company-types";
import { normalizeCompanyProfile } from "./company-types";

export interface CompanyOnboardingFileMeta {
  name: string;
  size: number;
  type: string;
  lastModified: number;
}

export interface CompanyOnboardingDraft {
  version: 1;
  updatedAt: string;
  step: number;
  companyName: string;
  website: string;
  companyChoice: CompanyCreationChoice;
  profilePath: CompanyProfilePath;
  selectedExistingCompanyId: number | null;
  workingCompany: CompanyBasicInfo | null;
  workingHasProfile: boolean;
  sourceStatuses: CompanySourceStatus[];
  portfolioFileMeta: CompanyOnboardingFileMeta[];
  institutionalFileMeta: CompanyOnboardingFileMeta[];
  sessionId: number | null;
  questions: CompanyInterviewQuestion[];
  answers: Record<number, CompanyInterviewAnswerValue>;
  summaryProfile: CompanyProfile;
}

export function buildCompanyOnboardingDraftKey(
  userId: string | null | undefined,
): string | null {
  return userId ? `company-onboarding-draft:user:${userId}` : null;
}

export function toFileMeta(file: File): CompanyOnboardingFileMeta {
  return {
    name: file.name,
    size: file.size,
    type: file.type,
    lastModified: file.lastModified,
  };
}

export function buildCompanyOnboardingDraft(
  draft: CompanyOnboardingDraft,
): CompanyOnboardingDraft {
  return {
    ...draft,
    version: 1,
    updatedAt: new Date().toISOString(),
    sourceStatuses: Array.isArray(draft.sourceStatuses)
      ? draft.sourceStatuses
      : [],
    portfolioFileMeta: Array.isArray(draft.portfolioFileMeta)
      ? draft.portfolioFileMeta
      : [],
    institutionalFileMeta: Array.isArray(draft.institutionalFileMeta)
      ? draft.institutionalFileMeta
      : [],
    questions: Array.isArray(draft.questions) ? draft.questions : [],
    answers:
      draft.answers && typeof draft.answers === "object" ? draft.answers : {},
    summaryProfile: normalizeCompanyProfile(draft.summaryProfile),
  };
}

export function createInitialSourceStatuses(
  website: string,
  portfolioFileMeta: CompanyOnboardingFileMeta[],
  institutionalFileMeta: CompanyOnboardingFileMeta[],
): CompanySourceStatus[] {
  return [
    {
      key: "website",
      label: "Website",
      status: website.trim() ? "not_added" : "not_added",
    },
    {
      key: "portfolio",
      label: "Portfolio",
      status: portfolioFileMeta.length ? "not_added" : "not_added",
    },
    {
      key: "institutional",
      label: "Documentos institucionais",
      status: institutionalFileMeta.length ? "not_added" : "not_added",
    },
  ];
}

export function loadCompanyOnboardingDraft(
  draftKey: string | null,
): CompanyOnboardingDraft | null {
  if (!draftKey || typeof window === "undefined") return null;

  const raw = window.localStorage.getItem(draftKey);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as Partial<CompanyOnboardingDraft>;
    if (parsed.version !== 1) return null;
    return buildCompanyOnboardingDraft({
      version: 1,
      updatedAt: String(parsed.updatedAt ?? ""),
      step: typeof parsed.step === "number" ? parsed.step : 0,
      companyName: String(parsed.companyName ?? ""),
      website: String(parsed.website ?? ""),
      companyChoice: parsed.companyChoice ?? null,
      profilePath: parsed.profilePath ?? null,
      selectedExistingCompanyId:
        typeof parsed.selectedExistingCompanyId === "number"
          ? parsed.selectedExistingCompanyId
          : null,
      workingCompany: parsed.workingCompany ?? null,
      workingHasProfile: Boolean(parsed.workingHasProfile),
      sourceStatuses: Array.isArray(parsed.sourceStatuses)
        ? parsed.sourceStatuses
        : [],
      portfolioFileMeta: Array.isArray(parsed.portfolioFileMeta)
        ? parsed.portfolioFileMeta
        : [],
      institutionalFileMeta: Array.isArray(parsed.institutionalFileMeta)
        ? parsed.institutionalFileMeta
        : [],
      sessionId: typeof parsed.sessionId === "number" ? parsed.sessionId : null,
      questions: Array.isArray(parsed.questions) ? parsed.questions : [],
      answers:
        parsed.answers && typeof parsed.answers === "object"
          ? parsed.answers
          : {},
      summaryProfile: normalizeCompanyProfile(parsed.summaryProfile),
    });
  } catch {
    return null;
  }
}

export function saveCompanyOnboardingDraft(
  draftKey: string | null,
  draft: CompanyOnboardingDraft,
): void {
  if (!draftKey || typeof window === "undefined") return;
  window.localStorage.setItem(
    draftKey,
    JSON.stringify(buildCompanyOnboardingDraft(draft)),
  );
}

export function clearCompanyOnboardingDraft(draftKey: string | null): void {
  if (!draftKey || typeof window === "undefined") return;
  window.localStorage.removeItem(draftKey);
}

export function draftHasProgress(draft: CompanyOnboardingDraft | null): boolean {
  if (!draft) return false;

  return Boolean(
    draft.step > 0 ||
      draft.companyName.trim() ||
      draft.website.trim() ||
      draft.companyChoice ||
      draft.profilePath ||
      draft.selectedExistingCompanyId !== null ||
      draft.sourceStatuses.some((status) => status.status !== "not_added") ||
      draft.portfolioFileMeta.length > 0 ||
      draft.institutionalFileMeta.length > 0 ||
      draft.sessionId !== null ||
      Object.keys(draft.answers).length > 0 ||
      draft.questions.length > 0 ||
      draft.summaryProfile.company_id !== null,
  );
}

export function restoreSourceStatusDetails(
  sourceStatuses: CompanySourceStatus[],
  portfolioFileMeta: CompanyOnboardingFileMeta[],
  institutionalFileMeta: CompanyOnboardingFileMeta[],
): CompanySourceStatus[] {
  return sourceStatuses.map((status) => {
    if (status.key === "portfolio" && portfolioFileMeta.length > 0) {
      return {
        ...status,
        detail:
          status.status === "processed" || status.status === "partial"
            ? status.detail
            : "É necessário voltar a selecionar este ficheiro.",
      };
    }

    if (status.key === "institutional" && institutionalFileMeta.length > 0) {
      return {
        ...status,
        detail:
          status.status === "processed" || status.status === "partial"
            ? status.detail
            : "É necessário voltar a selecionar este ficheiro.",
      };
    }

    return status;
  });
}
