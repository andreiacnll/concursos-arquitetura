"use client";

type AnyRecord = Record<string, any>;

export type UniversalSubmission = {
  participantDocuments: AnyRecord[];
  proposalDocuments: AnyRecord[];
  formatsAndLimits: AnyRecord[];
  criticalConditions: AnyRecord[];
  postSelectionDocuments: AnyRecord[];
  contractDeliverables: AnyRecord[];
  sourceDocuments: AnyRecord[];
  documentsRead: number | null;
  sourceVersion: string;
};

export type DecisionCriterion = {
  key: string;
  label: string;
  weight: number | null;
  weightContext: string;
  globalWeight: number | null;
  profileDependent: boolean;
  status: "confirmed" | "missing" | "documented";
  statusLabel: string;
};

export function cleanUniversal(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value.replace(/\s+/g, " ").trim();
  if (typeof value === "number") return String(value);
  if (typeof value === "object") {
    const item = value as AnyRecord;
    return cleanUniversal(
      item.title ??
        item.titulo ??
        item.label ??
        item.name ??
        item.role ??
        item.requirement ??
        item.summary ??
        item.description ??
        item.descricao ??
        item.text ??
        item.value ??
        "",
    );
  }
  return String(value).trim();
}

function asRecord(value: unknown): AnyRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as AnyRecord)
    : {};
}

export function asUniversalArray(value: unknown): AnyRecord[] {
  return Array.isArray(value)
    ? value
        .filter((item) => item !== null && item !== undefined)
        .map((item) =>
          typeof item === "object"
            ? (item as AnyRecord)
            : { title: cleanUniversal(item) },
        )
    : [];
}

export function foldUniversal(value: unknown): string {
  return cleanUniversal(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function numberValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;

  const raw = cleanUniversal(value);
  if (!raw) return null;

  const normalized = raw
    .replace(/\s/g, "")
    .replace(/€/g, "")
    .replace(/%(.*)$/g, "")
    .replace(/\.(?=\d{3}(?:\D|$))/g, "")
    .replace(",", ".");

  const match = normalized.match(/-?\d+(?:\.\d+)?/);
  if (!match) return null;

  const parsed = Number(match[0]);
  return Number.isFinite(parsed) ? parsed : null;
}

function meaningful(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return Boolean(cleanUniversal(value));
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value as object).length > 0;
  return true;
}

function itemSignature(item: AnyRecord): string {
  const subfactor = foldUniversal(
    item?.subfactor_code ??
      item?.criterion_code ??
      item?.subcriterion_code,
  );

  if (subfactor) return `sub:${subfactor}`;

  const code = foldUniversal(item?.code);
  const title = foldUniversal(cleanUniversal(item));

  if (code && title) return `code:${code}|${title}`;
  if (title) return `title:${title}`;

  try {
    return `json:${JSON.stringify(item)}`;
  } catch {
    return "";
  }
}

function itemRichness(item: AnyRecord): number {
  let score = 0;

  for (const [key, value] of Object.entries(item || {})) {
    if (!meaningful(value)) continue;

    score += 2;

    if (
      [
        "summary",
        "description",
        "descricao",
        "requirement",
        "evidence_excerpt",
        "source_document",
        "source_heading",
      ].includes(key)
    ) {
      score += Math.min(30, cleanUniversal(value).length / 40);
    }
  }

  return score;
}

function mergeObjectsPreferRich(
  current: AnyRecord,
  candidate: AnyRecord,
): AnyRecord {
  const output: AnyRecord = { ...current };

  for (const [key, value] of Object.entries(candidate || {})) {
    if (!meaningful(value)) continue;

    const old = output[key];

    if (!meaningful(old)) {
      output[key] = value;
      continue;
    }

    if (
      typeof old === "string" &&
      typeof value === "string" &&
      cleanUniversal(value).length > cleanUniversal(old).length
    ) {
      output[key] = value;
    }
  }

  return output;
}

export function mergeUniversalItems(...values: unknown[]): AnyRecord[] {
  const byKey = new Map<string, AnyRecord>();
  const order: string[] = [];
  let anonymous = 0;

  for (const value of values) {
    for (const item of asUniversalArray(value)) {
      let key = itemSignature(item);

      if (!key) {
        key = `anonymous:${anonymous++}`;
      }

      const current = byKey.get(key);

      if (!current) {
        byKey.set(key, item);
        order.push(key);
        continue;
      }

      const primary =
        itemRichness(item) > itemRichness(current)
          ? item
          : current;

      const secondary = primary === item ? current : item;

      byKey.set(
        key,
        mergeObjectsPreferRich(primary, secondary),
      );
    }
  }

  return order.map((key) => byKey.get(key)!).filter(Boolean);
}

function mergeFactors(...values: unknown[]): AnyRecord[] {
  const byKey = new Map<string, AnyRecord>();
  const order: string[] = [];
  let anonymous = 0;

  for (const value of values) {
    for (const factor of asUniversalArray(value)) {
      const code = foldUniversal(factor?.code);
      const label = foldUniversal(
        factor?.label ?? factor?.name ?? factor?.title,
      );

      const key = code
        ? `code:${code}`
        : label
          ? `label:${label}`
          : `anonymous:${anonymous++}`;

      const current = byKey.get(key);

      if (!current) {
        byKey.set(key, {
          ...factor,
          subfactors: mergeUniversalItems(factor?.subfactors),
        });
        order.push(key);
        continue;
      }

      const primary =
        itemRichness(factor) > itemRichness(current)
          ? factor
          : current;
      const secondary = primary === factor ? current : factor;

      const merged = mergeObjectsPreferRich(primary, secondary);

      merged.subfactors = mergeUniversalItems(
        current?.subfactors,
        factor?.subfactors,
      );

      byKey.set(key, merged);
    }
  }

  return order.map((key) => byKey.get(key)!).filter(Boolean);
}

function pickMeaningful(...values: unknown[]): unknown {
  for (const value of values) {
    if (meaningful(value)) return value;
  }
  return undefined;
}

function mergeProcedureSections(sources: AnyRecord[]): AnyRecord {
  const root = sources[0] ?? {};
  const extraction = sources[1] ?? {};
  const insights = sources[2] ?? {};

  const base: AnyRecord = {
    ...insights,
    ...extraction,
    ...root,
  };

  const awards = sources.map((item) => asRecord(item?.award_criteria));
  const eligibilities = sources.map((item) => asRecord(item?.eligibility));
  const submissions = sources.map((item) => asRecord(item?.submission));
  const contracts = sources.map((item) => asRecord(item?.contract));

  const awardBase: AnyRecord = {
    ...awards[2],
    ...awards[1],
    ...awards[0],
  };

  awardBase.factors = mergeFactors(
    ...awards.map((item) => item?.factors),
  );
  awardBase.scoring_requirements = mergeUniversalItems(
    ...awards.map((item) => item?.scoring_requirements),
  );
  awardBase.tie_breakers = mergeUniversalItems(
    ...awards.map((item) => item?.tie_breakers),
  );

  const eligibilityBase: AnyRecord = {
    ...eligibilities[2],
    ...eligibilities[1],
    ...eligibilities[0],
  };

  eligibilityBase.explicit_exclusions = mergeUniversalItems(
    ...eligibilities.map((item) => item?.explicit_exclusions),
  );
  eligibilityBase.scoring_requirements = mergeUniversalItems(
    ...eligibilities.map((item) => item?.scoring_requirements),
  );
  eligibilityBase.eligibility_requirements = mergeUniversalItems(
    ...eligibilities.map((item) => item?.eligibility_requirements),
  );
  eligibilityBase.minimum_requirements = mergeUniversalItems(
    ...eligibilities.map((item) => item?.minimum_requirements),
  );

  const submissionBase: AnyRecord = {
    ...submissions[2],
    ...submissions[1],
    ...submissions[0],
  };

  for (const key of [
    "participant_documents",
    "documents",
    "checklist",
    "proposal_documents",
    "technical_content",
    "proposal_content",
    "formats_and_limits",
    "submission_rules",
    "formats",
    "critical_conditions",
    "post_selection_documents",
    "habilitation_documents",
    "team_requirements",
  ]) {
    submissionBase[key] = mergeUniversalItems(
      ...submissions.map((item) => item?.[key]),
    );
  }

  const contractBase: AnyRecord = {
    ...contracts[2],
    ...contracts[1],
    ...contracts[0],
  };

  for (const key of [
    "scope_services",
    "phases",
    "specialties",
    "technical_team",
    "payments",
    "payment_conditions",
    "deliverables",
    "risks",
  ]) {
    contractBase[key] = mergeUniversalItems(
      ...contracts.map((item) => item?.[key]),
    );
  }

  return {
    ...base,
    family: pickMeaningful(
      root?.family,
      extraction?.family,
      insights?.family,
    ),
    family_label: pickMeaningful(
      root?.family_label,
      extraction?.family_label,
      insights?.family_label,
    ),
    version: pickMeaningful(
      root?.version,
      extraction?.version,
      insights?.version,
    ),
    award_criteria: awardBase,
    eligibility: eligibilityBase,
    submission: submissionBase,
    contract: contractBase,
    technical_team: mergeUniversalItems(
      ...sources.map((item) => item?.technical_team),
    ),
    formal_risks: mergeUniversalItems(
      ...sources.map((item) => item?.formal_risks),
    ),
    document_gaps: mergeUniversalItems(
      ...sources.map((item) => item?.document_gaps),
    ),
    inconsistencies: mergeUniversalItems(
      ...sources.map((item) => item?.inconsistencies),
    ),
    documents: mergeUniversalItems(
      ...sources.map((item) => item?.documents),
    ),
    top_metrics: mergeUniversalItems(
      ...sources.map((item) => item?.top_metrics),
    ),
  };
}

function analysisBody(ficha: AnyRecord): AnyRecord {
  if (!ficha || typeof ficha !== "object") return {};
  return ficha;
}

export function getProcedureAnalysis(ficha: AnyRecord): AnyRecord {
  const root = analysisBody(ficha);
  const extraction = asRecord(root?.design_competition_extraction);
  const insights = asRecord(root?.document_insights);

  return mergeProcedureSections([
    asRecord(root?.procedure_analysis),
    asRecord(extraction?.procedure_analysis),
    asRecord(insights?.procedure_analysis),
  ]);
}

function documentAudit(ficha: AnyRecord): AnyRecord {
  return asRecord(
    ficha?.document_audit ??
      ficha?.document_insights?.document_audit ??
      {},
  );
}

function hasFormatMetadata(item: AnyRecord): boolean {
  return [
    item?.format,
    item?.page_size,
    item?.size,
    item?.orientation,
    item?.quantity,
    item?.max_pages,
    item?.maximum_pages,
    item?.maximum_size_mb,
    item?.max_file_size,
    item?.delivery_mode,
    item?.signature,
    item?.anonymity,
  ].some(meaningful);
}

export function buildUniversalSubmission(
  ficha: AnyRecord,
  procedureInput?: AnyRecord,
): UniversalSubmission {
  const root = analysisBody(ficha);
  const extraction = asRecord(root?.design_competition_extraction);

  const procedure =
    procedureInput && typeof procedureInput === "object"
      ? mergeProcedureSections([
          asRecord(procedureInput),
          asRecord(extraction?.procedure_analysis),
          asRecord(root?.document_insights?.procedure_analysis),
        ])
      : getProcedureAnalysis(root);

  const rootLegacy = asRecord(root?.submission_requirements);
  const extractionLegacy = asRecord(extraction?.submission_requirements);
  const rootGroups = asRecord(rootLegacy?.groups);
  const extractionGroups = asRecord(extractionLegacy?.groups);

  const submission = asRecord(procedure?.submission);
  const eligibility = asRecord(procedure?.eligibility);
  const contract = asRecord(procedure?.contract);
  const audit = documentAudit(root);

  const participantDocuments = mergeUniversalItems(
    rootGroups?.participant_documents,
    extractionGroups?.participant_documents,
    rootLegacy?.participant_documents,
    extractionLegacy?.participant_documents,
    submission?.participant_documents,
    submission?.documents,
    submission?.checklist,
  );

  const proposalDocuments = mergeUniversalItems(
    rootGroups?.design_work,
    extractionGroups?.design_work,
    rootLegacy?.proposal_documents,
    extractionLegacy?.proposal_documents,
    submission?.proposal_documents,
    submission?.technical_content,
    submission?.proposal_content,
  );

  const formatsFromProposal = proposalDocuments.filter(hasFormatMetadata);

  const formatsAndLimits = mergeUniversalItems(
    rootLegacy?.formats_and_limits,
    extractionLegacy?.formats_and_limits,
    rootGroups?.complementary_documents,
    extractionGroups?.complementary_documents,
    submission?.formats_and_limits,
    submission?.submission_rules,
    submission?.formats,
    formatsFromProposal,
  );

  const criticalConditions = mergeUniversalItems(
    rootLegacy?.critical_conditions,
    extractionLegacy?.critical_conditions,
    submission?.critical_conditions,
    eligibility?.explicit_exclusions,
    eligibility?.minimum_requirements,
    procedure?.formal_risks,
  );

  const postSelectionDocuments = mergeUniversalItems(
    rootGroups?.post_selection_documents,
    extractionGroups?.post_selection_documents,
    rootLegacy?.post_selection_documents,
    extractionLegacy?.post_selection_documents,
    submission?.post_selection_documents,
    submission?.habilitation_documents,
  );

  const contractDeliverables = mergeUniversalItems(
    rootGroups?.contract_deliverables,
    extractionGroups?.contract_deliverables,
    rootLegacy?.contract_deliverables,
    extractionLegacy?.contract_deliverables,
    contract?.deliverables,
    contract?.scope_services,
  );

  const official = asUniversalArray(audit?.official_documents_found);
  const accepted = official.filter(
    (item) =>
      item?.accepted_for_reader === true ||
      foldUniversal(item?.reader_status) === "accepted",
  );

  const sourceDocuments = mergeUniversalItems(
    accepted,
    rootLegacy?.source_documents_used,
    extractionLegacy?.source_documents_used,
    extraction?.source_documents_used,
    procedure?.documents,
  );

  const explicitRead = numberValue(
    rootLegacy?.documents_read ??
      extractionLegacy?.documents_read ??
      audit?.reader_accepted_documents ??
      audit?.documents_read,
  );

  const documentsRead =
    accepted.length > 0
      ? accepted.length
      : explicitRead !== null && explicitRead > 0
        ? explicitRead
        : sourceDocuments.length > 0
          ? sourceDocuments.length
          : null;

  return {
    participantDocuments,
    proposalDocuments,
    formatsAndLimits,
    criticalConditions,
    postSelectionDocuments,
    contractDeliverables,
    sourceDocuments,
    documentsRead,
    sourceVersion:
      cleanUniversal(rootLegacy?.version) ||
      cleanUniversal(extractionLegacy?.version) ||
      cleanUniversal(procedure?.version) ||
      "procedure-analysis",
  };
}

export function buildUniversalContract(
  ficha: AnyRecord,
  procedureInput?: AnyRecord,
): AnyRecord {
  const extraction = asRecord(ficha?.design_competition_extraction);

  const procedure =
    procedureInput && typeof procedureInput === "object"
      ? mergeProcedureSections([
          asRecord(procedureInput),
          asRecord(extraction?.procedure_analysis),
          asRecord(ficha?.document_insights?.procedure_analysis),
        ])
      : getProcedureAnalysis(ficha);

  const legacy = asRecord(extraction?.contract);
  const rootContract = asRecord(ficha?.contract);
  const current = asRecord(procedure?.contract);

  const phases = mergeUniversalItems(
    current?.phases,
    legacy?.phases,
    rootContract?.phases,
  );
  const specialties = mergeUniversalItems(
    current?.specialties,
    current?.technical_team,
    legacy?.specialties,
    rootContract?.specialties,
  );
  const payments = mergeUniversalItems(
    current?.payments,
    current?.payment_conditions,
    legacy?.payments,
    legacy?.payment_conditions,
    rootContract?.payments,
    rootContract?.payment_conditions,
  );
  const deliverables = mergeUniversalItems(
    current?.deliverables,
    legacy?.deliverables,
    rootContract?.deliverables,
  );
  const scopeServices = mergeUniversalItems(
    current?.scope_services,
    legacy?.scope_services,
    rootContract?.scope_services,
  );
  const risks = mergeUniversalItems(
    current?.risks,
    legacy?.risks,
    rootContract?.risks,
  );

  return {
    ...rootContract,
    ...legacy,
    ...current,
    phases,
    specialties,
    payments,
    deliverables,
    scope_services: scopeServices,
    risks,
    phase_count:
      numberValue(current?.phase_count) ??
      numberValue(legacy?.phase_count) ??
      numberValue(rootContract?.phase_count) ??
      (phases.length ? phases.length : null),
    specialty_count:
      numberValue(current?.specialty_count) ??
      numberValue(legacy?.specialty_count) ??
      numberValue(rootContract?.specialty_count) ??
      (specialties.length ? specialties.length : null),
  };
}

function factorWeight(item: AnyRecord): number | null {
  return numberValue(
    item?.display_weight_percent ??
      item?.published_weight_percent ??
      item?.internal_weight_percent ??
      item?.weight_percent ??
      item?.weight ??
      item?.percentage,
  );
}

function effectiveWeight(item: AnyRecord): number | null {
  return numberValue(
    item?.effective_weight_percent ??
      item?.global_weight_percent ??
      item?.absolute_weight,
  );
}

function canonicalFactors(
  ficha: AnyRecord,
  procedure: AnyRecord,
): AnyRecord[] {
  return mergeFactors(
    ficha?.analysis_canonical?.criteria?.factors,
    procedure?.award_criteria?.factors,
  );
}

function requirementsFor(ficha: AnyRecord): AnyRecord[] {
  return mergeUniversalItems(ficha?.analysis_canonical?.requirements);
}

function validCriterionLabel(value: unknown): boolean {
  const label = cleanUniversal(value);
  if (!label) return false;
  return /[A-Za-zÀ-ÿ0-9]/.test(label);
}

function sanitizeCriterionLabel(value: unknown): string {
  let label = cleanUniversal(value)
    .replace(/^\)+\s*/, "")
    .replace(/^\(+\s*/, "")
    .replace(/\s*\(\s*\d+(?:[.,]\d+)?\s*%\s*\)\s*$/i, "")
    .replace(/^\s*outros?\s+/i, "")
    .replace(/^\s*outro\s+nome\s*:\s*/i, "")
    .replace(/^\s*fator\s*\d+(?:[.,]\d+)?\s*:\s*/i, "")
    .replace(/^\s*crit[eé]rio\s*\d+(?:[.,]\d+)?\s*:\s*/i, "")
    .replace(/^[-–—:;,.\s]+/, "")
    .replace(/[-–—:;,.\s]+$/, "")
    .trim();

  label = label
    .replace(/^\s*outro\s+nome\s*:\s*/i, "")
    .replace(/^\s*fator\s*\d+(?:[.,]\d+)?\s*:\s*/i, "")
    .trim();

  return validCriterionLabel(label) ? label : "";
}

function factorIdentity(item: AnyRecord): string {
  return foldUniversal(item?.code) || foldUniversal(
    sanitizeCriterionLabel(item?.label ?? item?.name ?? item?.title),
  );
}

function findHierarchyMatch(
  factors: AnyRecord[],
  subfactorCode: string,
  label: string,
): { factor: AnyRecord | null; subfactor: AnyRecord | null } {
  const code = foldUniversal(subfactorCode);
  const foldedLabel = foldUniversal(label);

  for (const factor of factors) {
    for (const sub of asUniversalArray(factor?.subfactors)) {
      const subCode = foldUniversal(sub?.code);
      const subLabel = foldUniversal(
        sub?.label ?? sub?.name ?? sub?.title,
      );

      if (
        code &&
        subCode &&
        (
          code === subCode ||
          code.endsWith(subCode) ||
          subCode.endsWith(code)
        )
      ) {
        return { factor, subfactor: sub };
      }

      if (
        foldedLabel &&
        subLabel &&
        (
          foldedLabel === subLabel ||
          foldedLabel.includes(subLabel) ||
          subLabel.includes(foldedLabel)
        )
      ) {
        return { factor, subfactor: sub };
      }
    }
  }

  return { factor: null, subfactor: null };
}

function linkedRequirements(
  requirements: AnyRecord[],
  subfactorCode: string,
  factorCode = "",
): AnyRecord[] {
  const sub = foldUniversal(subfactorCode);
  const factor = foldUniversal(factorCode);

  return requirements.filter((requirement) => {
    const reqSub = foldUniversal(requirement?.subfactor_code);
    const reqFactor = foldUniversal(requirement?.factor_code);

    if (sub && reqSub) {
      return (
        sub === reqSub ||
        sub.endsWith(reqSub) ||
        reqSub.endsWith(sub)
      );
    }

    if (factor && reqFactor) {
      return (
        factor === reqFactor ||
        factor.endsWith(reqFactor) ||
        reqFactor.endsWith(factor)
      );
    }

    return false;
  });
}

function requirementStatus(requirements: AnyRecord[]): {
  status: "confirmed" | "missing" | "documented";
  label: string;
} {
  if (!requirements.length) {
    return {
      status: "documented",
      label: "Critério confirmado nas peças",
    };
  }

  const statuses = requirements.map((requirement) =>
    foldUniversal(
      requirement?.result?.status ??
        requirement?.profile?.status ??
        requirement?.status,
    ),
  );

  const allConfirmed = statuses.every((status) =>
    ["met", "confirmed", "cumpre", "comprovado"].includes(status),
  );

  if (allConfirmed) {
    return {
      status: "confirmed",
      label: "Dados confirmados no perfil",
    };
  }

  return {
    status: "missing",
    label: "Completar dados do perfil",
  };
}

function scoringCandidates(
  ficha: AnyRecord,
  procedure: AnyRecord,
): AnyRecord[] {
  const requirements = requirementsFor(ficha).filter((item) => {
    if (item?.profile_dependent !== true) return false;
    if (foldUniversal(item?.phase) === "execution") return false;

    const nature = foldUniversal(item?.nature);
    return nature === "evaluation" || nature === "team";
  });

  return mergeUniversalItems(
    requirements,
    procedure?.award_criteria?.scoring_requirements,
    procedure?.eligibility?.scoring_requirements,
  ).filter((item) => {
    const code = cleanUniversal(
      item?.subfactor_code ??
        item?.criterion_code ??
        item?.subcriterion_code,
    );

    const nature = foldUniversal(item?.nature);
    const profileDependent = item?.profile_dependent === true;

    return Boolean(
      code ||
        factorWeight(item) !== null ||
        effectiveWeight(item) !== null ||
        profileDependent ||
        nature === "evaluation" ||
        nature === "team",
    );
  });
}

function scoringRows(
  ficha: AnyRecord,
  procedure: AnyRecord,
): DecisionCriterion[] {
  const factors = canonicalFactors(ficha, procedure);
  const requirements = requirementsFor(ficha);
  const candidates = scoringCandidates(ficha, procedure);

  const output: DecisionCriterion[] = [];
  const seen = new Set<string>();

  for (const item of candidates) {
    const subfactorCode = cleanUniversal(
      item?.subfactor_code ??
        item?.criterion_code ??
        item?.subcriterion_code ??
        item?.code,
    );

    const rawLabel = cleanUniversal(
      item?.title ??
        item?.titulo ??
        item?.label ??
        item?.role ??
        item?.requirement ??
        item?.summary,
    );

    const match = findHierarchyMatch(
      factors,
      subfactorCode,
      rawLabel,
    );

    const hierarchyLabel = sanitizeCriterionLabel(
      match?.subfactor?.label ??
        match?.subfactor?.name ??
        match?.subfactor?.title,
    );

    const candidateLabel = sanitizeCriterionLabel(rawLabel);

    const label =
      candidateLabel &&
      (
        !hierarchyLabel ||
        candidateLabel.length >= hierarchyLabel.length
      )
        ? candidateLabel
        : hierarchyLabel;

    if (!label) continue;

    const code =
      cleanUniversal(match?.subfactor?.code) ||
      subfactorCode;

    const parentCode = cleanUniversal(match?.factor?.code);

    const linked = linkedRequirements(
      requirements,
      code,
      parentCode,
    );

    const status = requirementStatus(linked);

    const published =
      factorWeight(match?.subfactor ?? {}) ??
      factorWeight(item);

    const parentWeight = factorWeight(match?.factor ?? {});

    let global =
      effectiveWeight(match?.subfactor ?? {}) ??
      effectiveWeight(item);

    if (
      global === null &&
      published !== null &&
      parentWeight !== null &&
      asUniversalArray(match?.factor?.subfactors).length > 0
    ) {
      global = (parentWeight * published) / 100;
    }

    const context =
      match?.subfactor &&
      parentWeight !== null
        ? cleanUniversal(match?.subfactor?.weight_context) || "do fator"
        : "da avaliação";

    const key = code
      ? `sub:${foldUniversal(code)}`
      : `label:${foldUniversal(label)}`;

    if (seen.has(key)) continue;
    seen.add(key);

    const profileLinked =
      linked.length > 0 ||
      item?.profile_dependent === true;

    output.push({
      key,
      label,
      weight: published ?? global,
      weightContext: context,
      globalWeight: global,
      profileDependent: profileLinked,
      status: profileLinked ? status.status : "documented",
      statusLabel: profileLinked
        ? status.label
        : "Critério confirmado nas peças",
    });
  }

  return output;
}

function parsedSummaryCriteria(summary: string): DecisionCriterion[] {
  if (!summary) return [];

  const segments = summary
    .split(/[•·;\n]+/)
    .map((item) => cleanUniversal(item))
    .filter(Boolean);

  const output: DecisionCriterion[] = [];
  const seen = new Set<string>();

  for (const segment of segments) {
    const matches = [
      ...segment.matchAll(/(\d+(?:[.,]\d+)?)\s*%/g),
    ];

    if (!matches.length) continue;

    const match = matches[matches.length - 1];
    const weight = numberValue(match[1]);

    if (weight === null) continue;

    let labelPart = segment.slice(
      0,
      match.index ?? segment.length,
    );

    labelPart = labelPart
      .replace(/\(\s*\d+(?:[.,]\d+)?\s*%\s*\)\s*$/i, "")
      .trim();

    const label = sanitizeCriterionLabel(labelPart);

    if (!label) continue;

    const key = `${foldUniversal(label)}|${weight}`;

    if (seen.has(key)) continue;
    seen.add(key);

    output.push({
      key: `summary:${key}`,
      label,
      weight,
      weightContext: "da avaliação",
      globalWeight: weight,
      profileDependent: false,
      status: "documented",
      statusLabel: "Critério confirmado nas peças",
    });
  }

  return output;
}

function topLevelRows(
  ficha: AnyRecord,
  procedure: AnyRecord,
  criteriaSummary = "",
): DecisionCriterion[] {
  const factors = canonicalFactors(ficha, procedure);
  const output: DecisionCriterion[] = [];

  for (const factor of factors) {
    const label = sanitizeCriterionLabel(
      factor?.label ?? factor?.name ?? factor?.title,
    );
    const weight = factorWeight(factor);

    if (!label || weight === null) continue;

    output.push({
      key: `factor:${factorIdentity(factor)}`,
      label,
      weight,
      weightContext: "da avaliação",
      globalWeight: weight,
      profileDependent: false,
      status: "documented",
      statusLabel: "Critério confirmado nas peças",
    });
  }

  const fallback = parsedSummaryCriteria(
    cleanUniversal(criteriaSummary) ||
      cleanUniversal(procedure?.award_criteria?.summary),
  );

  if (!output.length) return fallback;

  const merged = [...output];

  for (const item of fallback) {
    const folded = foldUniversal(item.label);

    const duplicate = merged.some((current) => {
      const probe = foldUniversal(current.label);
      return (
        probe === folded ||
        probe.includes(folded) ||
        folded.includes(probe)
      );
    });

    if (!duplicate) merged.push(item);
  }

  return merged;
}

export function buildDecisionCriteria(
  ficha: AnyRecord,
  procedureInput?: AnyRecord,
  criteriaSummary = "",
): DecisionCriterion[] {
  const procedure =
    procedureInput && typeof procedureInput === "object"
      ? mergeProcedureSections([
          asRecord(procedureInput),
          asRecord(ficha?.design_competition_extraction?.procedure_analysis),
          asRecord(ficha?.document_insights?.procedure_analysis),
        ])
      : getProcedureAnalysis(ficha);

  const scored = scoringRows(ficha, procedure);

  // Se existem critérios de equipa/experiência pontuados, são estes que
  // interessam à decisão. Não misturamos Preço nem fatores genéricos.
  if (scored.length) return scored;

  return topLevelRows(
    ficha,
    procedure,
    criteriaSummary,
  );
}

function prettyWeight(value: number): string {
  if (Math.abs(value - Math.round(value)) < 0.0001) {
    return String(Math.round(value));
  }

  return value.toFixed(1).replace(".", ",");
}

export function buildCriteriaSummary(
  ficha: AnyRecord,
  procedureInput?: AnyRecord,
  fallbackSummary = "",
): string {
  const procedure =
    procedureInput && typeof procedureInput === "object"
      ? mergeProcedureSections([
          asRecord(procedureInput),
          asRecord(ficha?.design_competition_extraction?.procedure_analysis),
          asRecord(ficha?.document_insights?.procedure_analysis),
        ])
      : getProcedureAnalysis(ficha);

  const rows = topLevelRows(
    ficha,
    procedure,
    fallbackSummary,
  );

  if (!rows.length) {
    return cleanUniversal(fallbackSummary) || "Por confirmar";
  }

  return rows
    .slice(0, 6)
    .map((item) =>
      item.weight !== null
        ? `${item.label} ${prettyWeight(item.weight)}%`
        : item.label,
    )
    .join(" • ");
}

// CNLL_PROCEDURE_CARD_MATERIALIZER_V17_9B
function canonicalRequirementDisplayV179B(item: AnyRecord): AnyRecord {
  const required = item?.required ?? {};
  const target = item?.profile_target ?? {};

  return {
    ...item,
    title:
      cleanUniversal(item?.label) ||
      cleanUniversal(item?.title) ||
      cleanUniversal(required?.text) ||
      cleanUniversal(target?.role) ||
      "Requisito identificado",
    summary:
      cleanUniversal(item?.summary) ||
      cleanUniversal(required?.text) ||
      cleanUniversal(item?.source?.excerpt),
  };
}

function legacyLooksScoredV179B(item: AnyRecord): boolean {
  const probe = foldUniversal(
    [
      item?.titulo,
      item?.title,
      item?.label,
      item?.descricao,
      item?.description,
      item?.summary,
      item?.weight_percent,
      item?.percentage,
      item?.points,
    ].filter(Boolean).join(" "),
  );

  return (
    probe.includes("subfator") ||
    probe.includes("subfactor") ||
    probe.includes("pontu") ||
    probe.includes("ponto") ||
    item?.weight_percent !== undefined ||
    item?.percentage !== undefined ||
    item?.points !== undefined
  );
}

export function buildProcedureCardAnalysis(
  ficha: AnyRecord,
  procedureInput?: AnyRecord,
): AnyRecord {
  const procedure =
    procedureInput && typeof procedureInput === "object"
      ? procedureInput
      : getProcedureAnalysis(ficha);

  const canonicalRequirements = asUniversalArray(
    ficha?.analysis_canonical?.requirements,
  );

  const canonicalEligibility = canonicalRequirements
    .filter((item) => {
      if (foldUniversal(item?.phase) === "execution") return false;
      return foldUniversal(item?.nature) === "eligibility";
    })
    .map(canonicalRequirementDisplayV179B);

  const canonicalScoring = canonicalRequirements
    .filter((item) => {
      if (foldUniversal(item?.phase) === "execution") return false;
      if (item?.profile_dependent !== true) return false;
      const nature = foldUniversal(item?.nature);
      return nature === "evaluation" || nature === "team";
    })
    .map(canonicalRequirementDisplayV179B);

  const canonicalTeam = canonicalRequirements
    .filter((item) => {
      if (foldUniversal(item?.phase) === "execution") return false;
      const nature = foldUniversal(item?.nature);
      const scope = foldUniversal(item?.profile_target?.scope);
      return nature === "team" || scope === "person";
    })
    .map(canonicalRequirementDisplayV179B);

  const legacyTeam = asUniversalArray(ficha?.equipa);
  const legacyScoring = legacyTeam.filter(legacyLooksScoredV179B);

  const award = procedure?.award_criteria ?? {};
  const eligibility = procedure?.eligibility ?? {};
  const submission = procedure?.submission ?? {};
  const contract = procedure?.contract ?? {};

  const scoring = mergeUniversalItems(
    award?.scoring_requirements,
    eligibility?.scoring_requirements,
    canonicalScoring,
    legacyScoring,
  );

  const team = mergeUniversalItems(
    procedure?.technical_team,
    submission?.team_requirements,
    contract?.technical_team,
    canonicalTeam,
    legacyTeam,
  );

  const exclusions = mergeUniversalItems(
    eligibility?.explicit_exclusions,
    eligibility?.eligibility_requirements,
    eligibility?.minimum_requirements,
    submission?.critical_conditions,
    canonicalEligibility,
  );

  return {
    ...procedure,
    award_criteria: {
      ...award,
      scoring_requirements: scoring,
    },
    eligibility: {
      ...eligibility,
      explicit_exclusions: exclusions,
      scoring_requirements: scoring,
    },
    technical_team: team,
    canonical_criteria:
      ficha?.analysis_canonical?.criteria ?? null,
    canonical_requirements: canonicalRequirements,
  };
}
