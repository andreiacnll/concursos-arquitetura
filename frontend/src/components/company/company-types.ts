export interface CompanyIdentity {
  company_name: string;
  description: string;
  location: string;
  website: string;
}

export interface CompanyProjectExperience {
  name: string;
  typology: string;
  location: string;
  skills_demonstrated: string[];
  normalized_typology?: string;
  original_typology?: string;
  source?: string;
}

export interface CompanyTypologyExperience {
  typology: string;
  project_count: number;
  experience_level: string;
  experience_level_score: number;
  origins: string[];
  confidence: number;
  projects: CompanyProjectExperience[];
}

export interface CompanyPreferences {
  typologies: string[];
  procedures: string[];
  locations: string[];
  project_scale: string[];
}

export interface CompanyStrategy {
  priority_areas: string[];
  secondary_areas: string[];
  avoid_areas: string[];
  future_goals: string[];
}

export interface CompanyMemory {
  confirmed_facts: string[];
  assumptions: string[];
  validated_preferences: string[];
  open_questions: string[];
}

export interface CompanyProfile {
  company_id: number | null;
  identity: CompanyIdentity;
  services: string[];
  competences: string[];
  specializations: string[];
  project_experience: CompanyProjectExperience[];
  project_experience_summary?: CompanyTypologyExperience[];
  project_experience_counts?: Record<string, number>;
  project_counts_by_typology?: Record<string, number>;
  preferences: CompanyPreferences;
  strategy: CompanyStrategy;
  ai_memory: CompanyMemory;
}

export interface CompanyBasicInfo {
  id: number | null;
  name: string;
  website: string;
  owner_user_id?: string;
}

export interface CompanySearchResult {
  id: number;
  name: string;
  website: string;
  association_status: "owner" | "member" | "not_associated" | string;
}

export type CompanyCreationChoice = "new" | "existing" | null;
export type CompanyProfilePath = "import" | "manual" | null;
export type CompanyInterviewQuestionType =
  | "boolean_confirmation"
  | "single_choice"
  | "multi_choice"
  | "free_text";
export type CompanySourceProcessingStatus =
  | "not_added"
  | "processing"
  | "processed"
  | "partial"
  | "no_results"
  | "error";

export type CompanyInterviewAnswerValue =
  | string
  | boolean
  | string[]
  | number
  | null
  | Record<string, unknown>;

export interface CompanySourceStatus {
  key: string;
  label: string;
  status: CompanySourceProcessingStatus;
  detail?: string;
  name?: string;
  origin?: string;
  submitted_at?: string;
  facts_created?: number;
  projects_found?: number;
  pages_visited?: number;
  services_found?: string[];
  competences_found?: string[];
  warnings?: string[];
}

export interface CompanySourceSummary {
  key: string;
  label: string;
  source_type: string;
  source: string;
  name: string;
  origin: string;
  status: CompanySourceProcessingStatus;
  submitted_at: string | null;
  facts_count: number;
  projects_count: number;
  pages_visited?: number | null;
  services_found?: string[];
  competences_found?: string[];
  projects_found?: string[];
  warnings?: string[];
}

export interface CompanyWebsiteIngestionResult {
  status: "success" | "partial" | "failed" | string;
  source_url?: string;
  pages_visited?: number;
  facts_created?: number;
  projects_found?: string[];
  services_found?: string[];
  competences_found?: string[];
  warnings?: string[];
}

export interface CompanyInterviewQuestion {
  id: number;
  session_id: number;
  field: string;
  question: string;
  reason?: string | null;
  type?: CompanyInterviewQuestionType | null;
  question_type?: CompanyInterviewQuestionType | null;
  priority?: string | null;
  options?: Array<{ value: string; label: string }>;
  question_source?: "discovery" | "validation";
  knowledge_fact_id?: number | null;
  answer?: unknown;
  source?: string | null;
  evidence?: string | null;
  confidence?: number | null;
  suggested_answer?: CompanyInterviewAnswerValue;
}

export interface CompanyMemberProfileIdentity {
  name: string;
  role: string;
  specialization: string;
  education: string;
}

export interface CompanyMemberProfileExperience {
  projects: string[];
  typologies: string[];
  sectors: string[];
  responsibilities: string[];
}

export interface CompanyMemberProfileCompetences {
  technical: string[];
  software: string[];
  methodologies: string[];
}

export interface CompanyMemberProfilePreferences {
  preferred_typologies: string[];
  preferred_sectors: string[];
  preferred_locations: string[];
}

export interface CompanyMemberProfileGoals {
  career_goals: string[];
  development_areas: string[];
}

export interface CompanyMemberProfileVisibility {
  company_visible: string[];
  private: string[];
}

export interface CompanyMemberProfile {
  id: number | null;
  member_id: number | null;
  identity: CompanyMemberProfileIdentity;
  experience: CompanyMemberProfileExperience;
  competences: CompanyMemberProfileCompetences;
  preferences: CompanyMemberProfilePreferences;
  goals: CompanyMemberProfileGoals;
  visibility: CompanyMemberProfileVisibility;
}

const DEFAULT_PROFILE: CompanyProfile = {
  company_id: null,
  identity: {
    company_name: "",
    description: "",
    location: "",
    website: "",
  },
  services: [],
  competences: [],
  specializations: [],
  project_experience: [],
  preferences: {
    typologies: [],
    procedures: [],
    locations: [],
    project_scale: [],
  },
  strategy: {
    priority_areas: [],
    secondary_areas: [],
    avoid_areas: [],
    future_goals: [],
  },
  ai_memory: {
    confirmed_facts: [],
    assumptions: [],
    validated_preferences: [],
    open_questions: [],
  },
};

const DEFAULT_MEMBER_PROFILE: CompanyMemberProfile = {
  id: null,
  member_id: null,
  identity: {
    name: "",
    role: "",
    specialization: "",
    education: "",
  },
  experience: {
    projects: [],
    typologies: [],
    sectors: [],
    responsibilities: [],
  },
  competences: {
    technical: [],
    software: [],
    methodologies: [],
  },
  preferences: {
    preferred_typologies: [],
    preferred_sectors: [],
    preferred_locations: [],
  },
  goals: {
    career_goals: [],
    development_areas: [],
  },
  visibility: {
    company_visible: [],
    private: [],
  },
};

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];

  const seen = new Set<string>();
  const result: string[] = [];

  for (const item of value) {
    const text = String(item ?? "").trim();
    if (!text) continue;
    const key = text.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(text);
  }

  return result;
}

function toProjectArray(value: unknown): CompanyProjectExperience[] {
  if (!Array.isArray(value)) return [];

  return value.map((item) => {
    const project = (item ?? {}) as Partial<CompanyProjectExperience>;
    return {
      name: String(project.name ?? ""),
      typology: String(project.typology ?? ""),
      location: String(project.location ?? ""),
      skills_demonstrated: toStringArray(project.skills_demonstrated),
      normalized_typology: String(project.normalized_typology ?? ""),
      original_typology: String(project.original_typology ?? ""),
      source: String(project.source ?? ""),
    };
  });
}

export function createEmptyCompanyProfile(): CompanyProfile {
  return JSON.parse(JSON.stringify(DEFAULT_PROFILE)) as CompanyProfile;
}

export function createEmptyCompanyMemberProfile(): CompanyMemberProfile {
  return JSON.parse(JSON.stringify(DEFAULT_MEMBER_PROFILE)) as CompanyMemberProfile;
}

export function normalizeCompanyProfile(
  data: unknown,
): CompanyProfile {
  const raw = (data ?? {}) as Partial<CompanyProfile>;
  const defaults = createEmptyCompanyProfile();

  return {
    ...defaults,
    ...raw,
    company_id:
      typeof raw.company_id === "number" ? raw.company_id : defaults.company_id,
    identity: {
      ...defaults.identity,
      ...(raw.identity ?? {}),
    },
    services: toStringArray(raw.services),
    competences: toStringArray(raw.competences),
    specializations: toStringArray(raw.specializations),
    project_experience: toProjectArray(raw.project_experience),
    preferences: {
      ...defaults.preferences,
      ...(raw.preferences ?? {}),
      typologies: toStringArray(raw.preferences?.typologies),
      procedures: toStringArray(raw.preferences?.procedures),
      locations: toStringArray(raw.preferences?.locations),
      project_scale: toStringArray(raw.preferences?.project_scale),
    },
    strategy: {
      ...defaults.strategy,
      ...(raw.strategy ?? {}),
      priority_areas: toStringArray(raw.strategy?.priority_areas),
      secondary_areas: toStringArray(raw.strategy?.secondary_areas),
      avoid_areas: toStringArray(raw.strategy?.avoid_areas),
      future_goals: toStringArray(raw.strategy?.future_goals),
    },
    ai_memory: {
      ...defaults.ai_memory,
      ...(raw.ai_memory ?? {}),
      confirmed_facts: toStringArray(raw.ai_memory?.confirmed_facts),
      assumptions: toStringArray(raw.ai_memory?.assumptions),
      validated_preferences: toStringArray(
        raw.ai_memory?.validated_preferences,
      ),
      open_questions: toStringArray(raw.ai_memory?.open_questions),
    },
  };
}

function toMemberArray(value: unknown): string[] {
  return toStringArray(value);
}

export function normalizeCompanyMemberProfile(
  data: unknown,
): CompanyMemberProfile {
  const raw = (data ?? {}) as Partial<CompanyMemberProfile>;
  const defaults = createEmptyCompanyMemberProfile();

  return {
    ...defaults,
    ...raw,
    id: typeof raw.id === "number" ? raw.id : defaults.id,
    member_id:
      typeof raw.member_id === "number" ? raw.member_id : defaults.member_id,
    identity: {
      ...defaults.identity,
      ...(raw.identity ?? {}),
      name: String(raw.identity?.name ?? ""),
      role: String(raw.identity?.role ?? ""),
      specialization: String(raw.identity?.specialization ?? ""),
      education: String(raw.identity?.education ?? ""),
    },
    experience: {
      ...defaults.experience,
      ...(raw.experience ?? {}),
      projects: toMemberArray(raw.experience?.projects),
      typologies: toMemberArray(raw.experience?.typologies),
      sectors: toMemberArray(raw.experience?.sectors),
      responsibilities: toMemberArray(raw.experience?.responsibilities),
    },
    competences: {
      ...defaults.competences,
      ...(raw.competences ?? {}),
      technical: toMemberArray(raw.competences?.technical),
      software: toMemberArray(raw.competences?.software),
      methodologies: toMemberArray(raw.competences?.methodologies),
    },
    preferences: {
      ...defaults.preferences,
      ...(raw.preferences ?? {}),
      preferred_typologies: toMemberArray(raw.preferences?.preferred_typologies),
      preferred_sectors: toMemberArray(raw.preferences?.preferred_sectors),
      preferred_locations: toMemberArray(raw.preferences?.preferred_locations),
    },
    goals: {
      ...defaults.goals,
      ...(raw.goals ?? {}),
      career_goals: toMemberArray(raw.goals?.career_goals),
      development_areas: toMemberArray(raw.goals?.development_areas),
    },
    visibility: {
      ...defaults.visibility,
      ...(raw.visibility ?? {}),
      company_visible: toMemberArray(raw.visibility?.company_visible),
      private: toMemberArray(raw.visibility?.private),
    },
  };
}

export function isCompanyProfileEmpty(profile: CompanyProfile): boolean {
  return (
    !String(profile.identity.company_name).trim() &&
    !String(profile.identity.description).trim() &&
    !String(profile.identity.location).trim() &&
    !String(profile.identity.website).trim() &&
    profile.services.length === 0 &&
    profile.competences.length === 0 &&
    profile.specializations.length === 0 &&
    profile.project_experience.length === 0 &&
    profile.strategy.priority_areas.length === 0 &&
    profile.strategy.secondary_areas.length === 0 &&
    profile.strategy.avoid_areas.length === 0 &&
    profile.strategy.future_goals.length === 0 &&
    profile.ai_memory.confirmed_facts.length === 0 &&
    profile.ai_memory.assumptions.length === 0 &&
    profile.ai_memory.validated_preferences.length === 0 &&
    profile.ai_memory.open_questions.length === 0
  );
}

export function needsCompanyOnboarding(profile: CompanyProfile): boolean {
  const identityFilled =
    Boolean(profile.identity.company_name.trim()) ||
    Boolean(profile.identity.website.trim()) ||
    Boolean(profile.identity.description.trim()) ||
    Boolean(profile.identity.location.trim());

  const foundationFilled =
    profile.services.length > 0 ||
    profile.competences.length > 0 ||
    profile.project_experience.length > 0 ||
    profile.strategy.priority_areas.length > 0 ||
    profile.strategy.future_goals.length > 0;

  return !identityFilled || !foundationFilled || isCompanyProfileEmpty(profile);
}

export function listToText(value: string[]): string {
  return value.join(", ");
}

export function textToList(value: string): string[] {
  return value
    .split(/[\n,;]+/g)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item, index, arr) => arr.findIndex((x) => x.toLowerCase() === item.toLowerCase()) === index);
}
