"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Save,
  X,
} from "lucide-react";
import { API_URL } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type AnyRecord = Record<string, any>;

type Props = {
  ficha: AnyRecord;
  concursoId: string;
  onFactsChange?: (facts: Record<string, AnyRecord>) => void;
};

const LOCAL_KEY = "cnll-analysis-profile-facts-v17-2";

function clean(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value).replace(/\s+/g, " ").trim();
}

function getReuseKey(question: AnyRecord): string {
  return clean(
    question?.profile_target?.reuse_key ??
      question?.required?.reuse_key ??
      question?.reuse_key,
  );
}

function questionMetric(question: AnyRecord): string {
  const direct = clean(question?.required?.metric);
  if (direct) return direct;

  for (const item of Array.isArray(question?.followups)
    ? question.followups
    : []) {
    const metric = clean(item?.metric);
    if (item?.type === "number" && metric) return metric;
  }

  return "";
}

function criterionImpact(canonical: AnyRecord, question: AnyRecord): number {
  const subCode = clean(question?.subfactor_code).toLowerCase();
  const factorCode = clean(question?.factor_code).toLowerCase();

  for (const factor of Array.isArray(canonical?.criteria?.factors)
    ? canonical.criteria.factors
    : []) {
    for (const sub of Array.isArray(factor?.subfactors)
      ? factor.subfactors
      : []) {
      if (subCode && clean(sub?.code).toLowerCase() === subCode) {
        const value = Number(
          sub?.effective_weight_percent ??
            sub?.display_weight_percent ??
            sub?.published_weight_percent ??
            0,
        );
        return Number.isFinite(value) ? value : 0;
      }
    }

    if (factorCode && clean(factor?.code).toLowerCase() === factorCode) {
      const value = Number(
        factor?.display_weight_percent ??
          factor?.published_weight_percent ??
          0,
      );
      return Number.isFinite(value) ? value : 0;
    }
  }

  return Number(question?.impact_weight_percent || 0);
}

function questionGroup(question: AnyRecord): string {
  const target = question?.profile_target || {};
  return [
    clean(question?.subfactor_code || question?.factor_code || question?.id),
    clean(target?.scope),
    clean(target?.role),
  ].join("|");
}

function priorityForNature(nature: string): number {
  const normalized = clean(nature).toLowerCase();
  if (normalized === "eligibility") return 0;
  if (normalized === "team") return 1;
  return 2;
}

function priorityLabel(nature: string): string {
  const normalized = clean(nature).toLowerCase();
  if (normalized === "eligibility") return "Elegibilidade";
  if (normalized === "team") return "Equipa";
  return "Pontuação";
}

function dedupeCanonicalQuestions(
  questions: AnyRecord[],
): AnyRecord[] {
  const seen = new Set<string>();
  const output: AnyRecord[] = [];

  for (const question of questions) {
    if (!question || typeof question !== "object") continue;

    const reuseKey = getReuseKey(question);
    const id = clean(question?.id);
    const text = clean(
      question?.text ||
        question?.question ||
        question?.prompt ||
        question?.label,
    );

    const signature =
      reuseKey ||
      id ||
      `${clean(question?.nature)}|${clean(question?.scope)}|${text}`.toLowerCase();

    if (!signature || seen.has(signature)) continue;
    seen.add(signature);
    output.push(question);
  }

  return output;
}

function curateQuestions(
  input: AnyRecord[],
  canonical: AnyRecord,
): AnyRecord[] {
  const requirements: AnyRecord[] = Array.isArray(canonical?.requirements)
    ? (canonical.requirements as AnyRecord[])
    : [];

  const requirementsById = new Map<string, AnyRecord>();
  for (const requirement of requirements) {
    const id = clean(requirement?.id);
    if (id) requirementsById.set(id, requirement);
  }

  const enriched: AnyRecord[] = input
    .map((original: AnyRecord): AnyRecord => {
      const ids = Array.isArray(original?.requirement_ids)
        ? original.requirement_ids.map(clean).filter(Boolean)
        : clean(original?.requirement_id)
          ? [clean(original.requirement_id)]
          : [];

      const linked = ids
        .map((id: string) => requirementsById.get(id))
        .filter((item): item is AnyRecord => Boolean(item));

      const linkedNatures = linked
        .map((item) => clean(item?.nature).toLowerCase())
        .filter(Boolean);

      const nature =
        linkedNatures.includes("eligibility")
          ? "eligibility"
          : linkedNatures.includes("team")
            ? "team"
            : linkedNatures.includes("evaluation")
              ? "evaluation"
              : linkedNatures.includes("submission")
                ? "submission"
                : linkedNatures.includes("habilitation")
                  ? "habilitation"
                  : clean(original?.nature).toLowerCase();

      const linkedPhases = linked
        .map((item) => clean(item?.phase).toLowerCase())
        .filter(Boolean);

      const phase =
        linkedPhases.includes("execution")
          ? "execution"
          : clean(original?.phase).toLowerCase() || "competition";

      const factorCode =
        clean(original?.factor_code) ||
        clean(linked[0]?.factor_code);

      const subfactorCode =
        clean(original?.subfactor_code) ||
        clean(linked[0]?.subfactor_code);

      const candidate: AnyRecord = {
        ...original,
        requirement_ids: ids,
        factor_code: factorCode,
        subfactor_code: subfactorCode,
        nature,
        phase,
      };

      const enrichedQuestion: AnyRecord = {
        ...candidate,
        impact_weight_percent: criterionImpact(canonical, candidate),
        priority_label: priorityLabel(nature),
      };
      return enrichedQuestion;
    })
    .filter((question: AnyRecord) => {
      const nature = clean(question?.nature).toLowerCase();
      const phase = clean(question?.phase).toLowerCase();

      if (phase === "execution") return false;
      if (nature === "submission" || nature === "habilitation") {
        return false;
      }

      if (nature === "eligibility" || nature === "team") {
        return true;
      }

      if (nature === "evaluation") {
        return Number(question?.impact_weight_percent || 0) > 0;
      }

      // Análises antigas sem natureza só sobrevivem se estiverem claramente
      // ligadas a um critério pontuado.
      return Number(question?.impact_weight_percent || 0) > 0;
    });

  const metricGroups = new Set<string>(
    enriched
      .filter((question: AnyRecord) => Boolean(questionMetric(question)))
      .map((question: AnyRecord) => questionGroup(question)),
  );

  const material: AnyRecord[] = enriched.filter((question: AnyRecord) => {
    if (
      !questionMetric(question) &&
      metricGroups.has(questionGroup(question))
    ) {
      return false;
    }
    return true;
  });

  const byKey = new Map<string, AnyRecord>();

  for (const original of material) {
    const key = getReuseKey(original) || clean(original?.id);
    if (!key) continue;

    const current = byKey.get(key);
    if (!current) {
      byKey.set(key, original);
      continue;
    }

    const requirementIds = Array.from(
      new Set([
        ...(Array.isArray(current?.requirement_ids)
          ? current.requirement_ids
          : []),
        ...(Array.isArray(original?.requirement_ids)
          ? original.requirement_ids
          : []),
      ]),
    );

    const contexts = [
      ...(Array.isArray(current?.contexts) ? current.contexts : []),
      ...(Array.isArray(original?.contexts) ? original.contexts : []),
    ];

    const followups = [
      ...(Array.isArray(current?.followups) ? current.followups : []),
    ];
    const signatures = new Set(
      followups.map(
        (item: AnyRecord) =>
          `${clean(item?.type)}|${clean(item?.metric)}|${clean(item?.label)}`,
      ),
    );

    for (const item of Array.isArray(original?.followups)
      ? original.followups
      : []) {
      const signature =
        `${clean(item?.type)}|${clean(item?.metric)}|${clean(item?.label)}`;
      if (!signatures.has(signature)) {
        followups.push(item);
        signatures.add(signature);
      }
    }

    byKey.set(key, {
      ...current,
      requirement_ids: requirementIds,
      contexts,
      followups,
      impact_weight_percent: Math.max(
        Number(current?.impact_weight_percent || 0),
        Number(original?.impact_weight_percent || 0),
      ),
    });
  }

  return Array.from(byKey.values()).sort((a, b) => {
    const priority =
      priorityForNature(a?.nature) - priorityForNature(b?.nature);
    if (priority !== 0) return priority;

    const impact =
      Number(b?.impact_weight_percent || 0) -
      Number(a?.impact_weight_percent || 0);
    if (impact !== 0) return impact;

    return clean(a?.subfactor_code || a?.factor_code).localeCompare(
      clean(b?.subfactor_code || b?.factor_code),
    );
  });
}

function readLocalFacts(): Record<string, AnyRecord> {
  if (typeof window === "undefined") return {};
  try {
    const parsed = JSON.parse(window.localStorage.getItem(LOCAL_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeLocalFacts(facts: Record<string, AnyRecord>) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LOCAL_KEY, JSON.stringify(facts));
  } catch {}
}

async function authToken(): Promise<string> {
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token || "";
}

async function readRemoteFacts(): Promise<Record<string, AnyRecord>> {
  const auth = await authToken();
  if (!auth) return {};

  const response = await fetch(
    `${API_URL}/company/analysis-facts?_=${Date.now()}`,
    {
      cache: "no-store",
      headers: { Authorization: `Bearer ${auth}` },
    },
  );
  if (!response.ok) return {};

  const payload = await response.json();
  const output: Record<string, AnyRecord> = {};
  for (const fact of Array.isArray(payload?.facts) ? payload.facts : []) {
    const key = clean(fact?.reuse_key);
    if (key) output[key] = fact;
  }
  return output;
}

async function saveRemoteFact(payload: AnyRecord): Promise<void> {
  const auth = await authToken();
  if (!auth) throw new Error("Sessão não encontrada.");

  const response = await fetch(`${API_URL}/company/analysis-facts`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${auth}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let message = "Não foi possível guardar a resposta no CV.";
    try {
      const body = await response.json();
      message = clean(body?.detail) || message;
    } catch {}
    throw new Error(message);
  }
}

async function recalculate(concursoId: string): Promise<void> {
  const auth = await authToken();
  if (!auth) throw new Error("Sessão não encontrada.");

  const response = await fetch(
    `${API_URL}/company/analysis-facts/recalculate/${concursoId}`,
    {
      method: "POST",
      cache: "no-store",
      headers: { Authorization: `Bearer ${auth}` },
    },
  );

  if (!response.ok) {
    let message = "As respostas foram guardadas, mas não foi possível recalcular a análise.";
    try {
      const body = await response.json();
      message = clean(body?.detail) || message;
    } catch {}
    throw new Error(message);
  }
}

async function ensureCanonical(concursoId: string): Promise<AnyRecord | null> {
  const auth = await authToken();
  if (!auth) return null;

  const response = await fetch(
    `${API_URL}/company/analysis-facts/ensure-canonical/${concursoId}`,
    {
      method: "POST",
      cache: "no-store",
      headers: { Authorization: `Bearer ${auth}` },
    },
  );

  if (!response.ok) return null;
  return response.json();
}

// CNLL_EDITABLE_QUESTIONS_FROM_REQUIREMENTS_V17_9B
function editableQuestionsFromRequirements(
  canonical: AnyRecord,
): AnyRecord[] {
  const requirements = Array.isArray(canonical?.requirements)
    ? canonical.requirements
    : [];

  const rebuilt: AnyRecord[] = [];

  for (const requirement of requirements) {
    if (!requirement || typeof requirement !== "object") continue;
    if (requirement?.profile_dependent !== true) continue;

    const nature = clean(requirement?.nature).toLowerCase();
    const phase = clean(requirement?.phase).toLowerCase();
    const stage = clean(requirement?.stage).toLowerCase();

    if (stage === "post_award") continue;
    if (phase === "execution") continue;
    if (nature === "submission" || nature === "habilitation") continue;

    const sourceQuestion =
      requirement?.question &&
      typeof requirement.question === "object"
        ? requirement.question
        : null;

    if (!sourceQuestion) continue;

    rebuilt.push({
      ...sourceQuestion,
      requirement_id:
        clean(requirement?.id) ||
        clean(sourceQuestion?.requirement_id) ||
        null,
      requirement_ids: Array.isArray(sourceQuestion?.requirement_ids)
        ? sourceQuestion.requirement_ids
        : clean(requirement?.id)
          ? [clean(requirement.id)]
          : [],
      factor_code:
        requirement?.factor_code ??
        sourceQuestion?.factor_code ??
        null,
      subfactor_code:
        requirement?.subfactor_code ??
        sourceQuestion?.subfactor_code ??
        null,
      nature:
        requirement?.nature ??
        sourceQuestion?.nature ??
        null,
      phase:
        requirement?.phase ??
        sourceQuestion?.phase ??
        "competition",
      stage:
        requirement?.stage ??
        sourceQuestion?.stage ??
        "pre_award",
      required:
        requirement?.required ??
        sourceQuestion?.required ??
        {},
      profile_target:
        requirement?.profile_target ??
        sourceQuestion?.profile_target ??
        {},
    });
  }

  return dedupeCanonicalQuestions(rebuilt);
}

function canonicalNeedsEnsure(ficha: AnyRecord): boolean {
  const canonical = ficha?.analysis_canonical;

  if (!canonical || typeof canonical !== "object") return true;

  const recoveryStatus = clean(canonical?.recovery_status);

  if (recoveryStatus === "no_procedural_evidence") {
    return false;
  }

  // CNLL_CANONICAL_VISIBLE_SYNC_V17_5_3B
  const procedures = [
    ficha?.procedure_analysis,
    ficha?.design_competition_extraction?.procedure_analysis,
  ];

  const visibleProcedureIsMaterial = procedures.some((procedure) => {
    if (!procedure || typeof procedure !== "object") return false;

    const award = procedure?.award_criteria;
    const factors = Array.isArray(award?.factors) ? award.factors : [];
    const scoring = Array.isArray(award?.scoring_requirements)
      ? award.scoring_requirements
      : [];
    const team = Array.isArray(procedure?.technical_team)
      ? procedure.technical_team
      : [];

    return factors.length > 0 || scoring.length > 0 || team.length > 0;
  });

  if (
    recoveryStatus.startsWith("recovered_from_") &&
    !visibleProcedureIsMaterial
  ) {
    return true;
  }

  const requirements = Array.isArray(canonical?.requirements)
    ? canonical.requirements
    : [];
  const questions = Array.isArray(canonical?.questions)
    ? canonical.questions
    : [];
  const factors = Array.isArray(canonical?.criteria?.factors)
    ? canonical.criteria.factors
    : [];

  const profileDependent = requirements.filter(
    (item: AnyRecord) => item?.profile_dependent === true,
  );

  if (
    visibleProcedureIsMaterial &&
    questions.length === 0 &&
    profileDependent.length === 0
  ) {
    return true;
  }

  return (
    requirements.length === 0 &&
    questions.length === 0 &&
    factors.length === 0
  );
}

function existingAnswer(fact?: AnyRecord): "yes" | "no" | "" {
  const value = clean(fact?.answer ?? fact?.value?.answer).toLowerCase();
  if (value === "yes" || value === "sim") return "yes";
  if (value === "no" || value === "não" || value === "nao") return "no";
  return "";
}

function QuestionFields({
  question,
  value,
  onChange,
}: {
  question: AnyRecord;
  value: AnyRecord;
  onChange: (next: AnyRecord) => void;
}) {
  const answer = clean(value?.answer);
  const followups = Array.isArray(question?.followups)
    ? question.followups
    : [];

  const visible = followups.filter((item: AnyRecord) => {
    const when = Array.isArray(item?.required_when)
      ? item.required_when
      : [];
    return !when.length || Boolean(answer && when.includes(answer));
  });

  return (
    <>
      <div className="aqm-yesno">
        <button
          type="button"
          className={answer === "yes" ? "active" : ""}
          onClick={() => onChange({ ...value, answer: "yes" })}
        >
          Sim
        </button>
        <button
          type="button"
          className={answer === "no" ? "active" : ""}
          onClick={() => onChange({ ...value, answer: "no" })}
        >
          Não
        </button>
      </div>

      {visible.map((item: AnyRecord, index: number) => {
        if (item?.type === "person") {
          return (
            <label className="aqm-field" key={`${item?.id || "person"}-${index}`}>
              <span>{clean(item?.label) || "Quem?"}</span>
              <input
                value={value?.person ?? ""}
                placeholder={clean(item?.placeholder) || "Nome do elemento da equipa"}
                onChange={(event) =>
                  onChange({ ...value, person: event.target.value })
                }
              />
            </label>
          );
        }

        if (item?.type === "project") {
          return (
            <label className="aqm-field" key={`${item?.id || "project"}-${index}`}>
              <span>{clean(item?.label) || "Que projeto?"}</span>
              <input
                value={value?.project ?? ""}
                placeholder={clean(item?.placeholder) || "Projeto de referência"}
                onChange={(event) =>
                  onChange({ ...value, project: event.target.value })
                }
              />
            </label>
          );
        }

        if (item?.type === "number") {
          return (
            <label className="aqm-field" key={`${item?.id || "number"}-${index}`}>
              <span>{clean(item?.label) || "Qual é o valor real?"}</span>
              <div className="aqm-number">
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={
                    value?.numeric_value === null ||
                    value?.numeric_value === undefined
                      ? ""
                      : String(value.numeric_value)
                  }
                  placeholder={clean(item?.placeholder) || "0"}
                  onChange={(event) =>
                    onChange({
                      ...value,
                      numeric_value:
                        event.target.value === ""
                          ? null
                          : Number(event.target.value),
                    })
                  }
                />
                {item?.unit ? <em>{clean(item.unit)}</em> : null}
              </div>
            </label>
          );
        }

        return null;
      })}
    </>
  );
}

export default function AnalysisQuestionsModal({
  ficha,
  concursoId,
  onFactsChange,
}: Props) {
  const router = useRouter();
  const canonical = ficha?.analysis_canonical || {};
  const questions = useMemo(() => {
    const rawQuestions: AnyRecord[] = Array.isArray(canonical?.questions)
      ? canonical.questions
      : [];

    // CNLL_CANONICAL_QUESTIONS_SOURCE_V17_5_3B
    const policy = clean(canonical?.question_policy_version).toLowerCase();
    const recoveryStatus = clean(canonical?.recovery_status);

    const backendQuestionsAreAuthoritative =
      policy === "decision-facts-v17.3" ||
      recoveryStatus.startsWith("recovered_from_");

    if (backendQuestionsAreAuthoritative) {
      return dedupeCanonicalQuestions(rawQuestions);
    }

    return curateQuestions(rawQuestions, canonical);
  }, [canonical]);

  // CNLL_EFFECTIVE_MODAL_QUESTIONS_V17_10
  // Fonte única do modal: perguntas canónicas do backend + perguntas
  // reconstruíveis dos requisitos company/profile-dependent.
  const effectiveQuestions = useMemo(
    () =>
      dedupeCanonicalQuestions([
        ...questions,
        ...editableQuestionsFromRequirements(canonical),
      ]),
    [questions, canonical?.requirements],
  );

  const signature = useMemo(
    () =>
      effectiveQuestions
        .map(
          (question) =>
            `${getReuseKey(question)}:${clean(question?.required?.threshold)}`,
        )
        .join("|"),
    [effectiveQuestions],
  );

  const [facts, setFacts] = useState<Record<string, AnyRecord>>({});
  const [answers, setAnswers] = useState<Record<string, AnyRecord>>({});
  const [loaded, setLoaded] = useState(false);
  const [open, setOpen] = useState(false);
  const [editingAll, setEditingAll] = useState(false);
  const [index, setIndex] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [savedMessage, setSavedMessage] = useState("");

  useEffect(() => {
    let mounted = true;

    async function load() {
      if (canonicalNeedsEnsure(ficha)) {
        try {
          const ensured = await ensureCanonical(concursoId);
          if (ensured?.ok && ensured?.changed && mounted) {
            router.refresh();
            return;
          }
        } catch {
          // Se a migração não for possível, a análise existente continua visível.
        }
      }

      const local = readLocalFacts();
      let remote: Record<string, AnyRecord> = {};
      try {
        remote = await readRemoteFacts();
      } catch {}

      if (!mounted) return;
      const merged = { ...local, ...remote };
      setFacts(merged);
      writeLocalFacts(merged);
      onFactsChange?.(merged);

      const seeded: Record<string, AnyRecord> = {};
      for (const question of effectiveQuestions) {
        const key = getReuseKey(question);
        if (!key) continue;
        const fact = merged[key];
        seeded[key] = {
          answer: existingAnswer(fact),
          person: fact?.person ?? fact?.value?.person ?? "",
          project: fact?.project ?? fact?.value?.project ?? "",
          numeric_value:
            fact?.numeric_value ?? fact?.value?.numeric_value ?? null,
        };
      }
      setAnswers(seeded);
      setLoaded(true);

      // CNLL_POPUP_PENDING_V17_5
      // Calcula primeiro as duas situações. Antes, a existência de UMA resposta
      // reutilizável fazia refresh+return e podia impedir o popup mesmo quando
      // ainda existiam outras perguntas por responder.
      const hasReusableExistingFact = effectiveQuestions.some((question) => {
        const key = getReuseKey(question);
        return Boolean(key && merged[key]);
      });
      const hasPending = effectiveQuestions.some((question) => {
        const key = getReuseKey(question);
        return Boolean(key && !merged[key]);
      });

      if (hasReusableExistingFact) {
        try {
          await recalculate(concursoId);

          // Só refresca imediatamente quando não há nada por responder.
          // Se houver perguntas pendentes, mantém esta montagem viva para
          // abrir o popup; o save final fará o refresh normal.
          if (mounted && !hasPending) {
            router.refresh();
            return;
          }
        } catch {
          // O popup continua funcional mesmo que o recálculo automático falhe.
        }
      }

      if (hasPending && mounted) {
        setEditingAll(false);
        setIndex(0);
        setOpen(true);
      }
    }

    load();
    return () => {
      mounted = false;
    };
  }, [signature, concursoId]);

  const pendingQuestions = useMemo(
    () =>
      effectiveQuestions.filter((question) => {
        const key = getReuseKey(question);
        return key && !facts[key];
      }),
    [effectiveQuestions, facts],
  );

  const visibleQuestions = editingAll ? effectiveQuestions : pendingQuestions;
  const safeIndex = Math.min(
    index,
    Math.max(visibleQuestions.length - 1, 0),
  );
  const current = visibleQuestions[safeIndex];
  const currentKey = current ? getReuseKey(current) : "";
  const currentValue = currentKey ? answers[currentKey] || {} : {};

  function openEditor() {
    setEditingAll(true);
    setIndex(0);
    setError("");
    setSavedMessage("");
    setOpen(true);
  }

  async function saveAllVisible() {
    if (!visibleQuestions.length) {
      setOpen(false);
      return;
    }

    const unanswered = visibleQuestions.filter((question) => {
      const key = getReuseKey(question);
      return !clean(answers[key]?.answer);
    });

    if (unanswered.length) {
      setError("Responde Sim ou Não a todas as perguntas antes de guardar.");
      return;
    }

    setSaving(true);
    setError("");

    try {
      const updated = { ...facts };

      for (const question of visibleQuestions) {
        const key = getReuseKey(question);
        if (!key) continue;
        const value = answers[key] || {};

        const contexts = Array.isArray(question?.contexts)
          ? question.contexts
          : [];
        const title =
          clean(question?.text) ||
          clean(contexts[0]?.label) ||
          "Dado de análise";

        const payload = {
          reuse_key: key,
          target: question?.profile_target || {},
          requirement_id: clean(question?.requirement_id) || null,
          requirement_ids: Array.isArray(question?.requirement_ids)
            ? question.requirement_ids
            : [],
          title,
          description: clean(question?.reason),
          answer: value.answer,
          person: clean(value.person) || null,
          project: clean(value.project) || null,
          numeric_value:
            value.numeric_value === "" ||
            value.numeric_value === undefined
              ? null
              : value.numeric_value,
          metric: question?.required?.metric || null,
          unit: question?.required?.unit || null,
          confirmed_by_user: true,
          source: "analysis_question",
        };

        await saveRemoteFact(payload);
        updated[key] = payload;
      }

      setFacts(updated);
      writeLocalFacts(updated);
      onFactsChange?.(updated);

      await recalculate(concursoId);

      setSavedMessage(
        `${visibleQuestions.length} ${
          visibleQuestions.length === 1
            ? "resposta guardada"
            : "respostas guardadas"
        } no CV. A análise foi recalculada.`,
      );

      window.setTimeout(() => {
        setOpen(false);
        setEditingAll(false);
        setIndex(0);
        setSavedMessage("");
        router.refresh();
      }, 700);
    } catch (exc) {
      setError(
        exc instanceof Error ? exc.message : "Não foi possível guardar.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (!loaded || !effectiveQuestions.length) return null;

  return (
    <>
      <button type="button" className="aqm-reopen" onClick={openEditor}>
        {pendingQuestions.length
          ? `Completar análise · ${pendingQuestions.length}`
          : "Editar respostas da análise"}
      </button>

      {open ? (
        <div className="aqm-backdrop" role="presentation">
          <section className="aqm-modal" role="dialog" aria-modal="true">
            <button
              type="button"
              className="aqm-close"
              onClick={() => setOpen(false)}
              aria-label="Fechar"
            >
              <X size={18} />
            </button>

            <div className="aqm-head">
              <span>Completar análise</span>
              <h2>
                {!editingAll && pendingQuestions.length
                  ? `Faltam ${pendingQuestions.length} informações para avaliar este concurso`
                  : "Rever respostas desta análise"}
              </h2>
              <p>
                Cada facto é perguntado uma única vez. A resposta fica no CV
                empresarial, é reutilizada noutros concursos e recalcula esta
                análise imediatamente.
              </p>
            </div>

            {current ? (
              <>
                <div className="aqm-progress">
                  <strong>
                    {safeIndex + 1} de {visibleQuestions.length}
                  </strong>
                  <div>
                    <i
                      style={{
                        width: `${
                          ((safeIndex + 1) /
                            Math.max(visibleQuestions.length, 1)) *
                          100
                        }%`,
                      }}
                    />
                  </div>
                </div>

                <div className="aqm-question">
                  <div className="aqm-context">
                    {current?.priority_label ? (
                      <span>{clean(current.priority_label)}</span>
                    ) : null}
                    {current?.subfactor_code ? (
                      <span>{clean(current.subfactor_code)}</span>
                    ) : null}
                    {Array.isArray(current?.requirement_ids) &&
                    current.requirement_ids.length > 1 ? (
                      <small>
                        Um único valor será comparado automaticamente com{" "}
                        {current.requirement_ids.length} níveis/requisitos deste critério.
                      </small>
                    ) : current?.required?.text ? (
                      <small>{clean(current.required.text)}</small>
                    ) : null}
                  </div>

                  <h3>{clean(current?.text) || "Confirmar requisito"}</h3>

                  <QuestionFields
                    question={current}
                    value={currentValue}
                    onChange={(next) =>
                      setAnswers((previous) => ({
                        ...previous,
                        [currentKey]: next,
                      }))
                    }
                  />
                </div>

                {error ? <p className="aqm-error">{error}</p> : null}
                {savedMessage ? (
                  <p className="aqm-saved">
                    <CheckCircle2 size={16} />
                    {savedMessage}
                  </p>
                ) : null}

                <footer className="aqm-footer">
                  <button
                    type="button"
                    className="secondary"
                    disabled={safeIndex === 0}
                    onClick={() => {
                      setError("");
                      setIndex((value) => Math.max(0, value - 1));
                    }}
                  >
                    <ChevronLeft size={16} />
                    Anterior
                  </button>

                  {safeIndex < visibleQuestions.length - 1 ? (
                    <button
                      type="button"
                      className="primary"
                      disabled={!clean(currentValue?.answer)}
                      onClick={() => {
                        setError("");
                        setIndex((value) =>
                          Math.min(
                            visibleQuestions.length - 1,
                            value + 1,
                          ),
                        );
                      }}
                    >
                      Seguinte
                      <ChevronRight size={16} />
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="primary"
                      disabled={saving || !clean(currentValue?.answer)}
                      onClick={saveAllVisible}
                    >
                      <Save size={16} />
                      {saving ? "A guardar e recalcular…" : "Guardar respostas"}
                    </button>
                  )}
                </footer>
              </>
            ) : (
              <div className="aqm-complete">
                <CheckCircle2 size={24} />
                <strong>Não há perguntas por responder.</strong>
                <button type="button" onClick={() => setOpen(false)}>
                  Fechar
                </button>
              </div>
            )}
          </section>
        </div>
      ) : null}

      <style jsx global>{`
        .aqm-reopen { position: fixed; right: 24px; bottom: 24px; z-index: 850; padding: 11px 15px; border: 0; border-radius: 10px; background: #667d42; color: white; font-weight: 800; cursor: pointer; box-shadow: 0 8px 24px rgba(0,0,0,.14); }
        .aqm-backdrop { position: fixed; inset: 0; z-index: 900; background: rgba(23,27,20,.48); display: grid; place-items: center; padding: 20px; }
        .aqm-modal { width: min(680px, 100%); max-height: calc(100vh - 40px); overflow: auto; position: relative; background: white; border-radius: 18px; padding: 28px; box-shadow: 0 24px 80px rgba(0,0,0,.22); }
        .aqm-close { position: absolute; right: 18px; top: 18px; width: 36px; height: 36px; border: 1px solid #e3e5df; border-radius: 50%; background: white; display: grid; place-items: center; cursor: pointer; }
        .aqm-head span { color: #6b7d4f; font-size: 12px; font-weight: 900; text-transform: uppercase; letter-spacing: .08em; }
        .aqm-head h2 { margin: 7px 42px 8px 0; font-size: 24px; }
        .aqm-head p { margin: 0; color: #6e716a; line-height: 1.55; }
        .aqm-progress { display: grid; gap: 8px; margin: 22px 0; font-size: 12px; color: #666; }
        .aqm-progress > div { height: 5px; background: #edf0e8; border-radius: 99px; overflow: hidden; }
        .aqm-progress i { display: block; height: 100%; background: #70854e; border-radius: inherit; }
        .aqm-question { padding: 20px; background: #fafaf7; border: 1px solid #e7e8e2; border-radius: 14px; }
        .aqm-context { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
        .aqm-context span { padding: 4px 8px; border-radius: 6px; background: #e7eddd; color: #5e7240; font-size: 11px; font-weight: 900; }
        .aqm-context small { color: #777; line-height: 1.4; }
        .aqm-question h3 { margin: 14px 0 18px; font-size: 20px; line-height: 1.35; }
        .aqm-yesno { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .aqm-yesno button { min-height: 46px; border: 1px solid #d9ddd2; border-radius: 10px; background: white; font-weight: 900; cursor: pointer; }
        .aqm-yesno button.active { background: #667d42; border-color: #667d42; color: white; }
        .aqm-field { display: grid; gap: 7px; margin-top: 15px; }
        .aqm-field > span { font-size: 12px; font-weight: 800; color: #555a51; }
        .aqm-field input { width: 100%; min-height: 44px; border: 1px solid #d9ddd2; border-radius: 9px; padding: 0 12px; background: white; }
        .aqm-number { display: flex; align-items: center; gap: 9px; }
        .aqm-number input { flex: 1; }
        .aqm-number em { font-style: normal; color: #777; font-size: 12px; }
        .aqm-error { margin: 12px 0 0; color: #9d3f31; font-size: 12px; }
        .aqm-saved { display: flex; align-items: center; gap: 7px; margin: 12px 0 0; color: #55703d; font-size: 12px; font-weight: 700; }
        .aqm-footer { display: flex; justify-content: space-between; gap: 10px; margin-top: 20px; }
        .aqm-footer button { display: inline-flex; align-items: center; justify-content: center; gap: 6px; min-height: 42px; padding: 0 15px; border-radius: 9px; font-weight: 800; cursor: pointer; }
        .aqm-footer .secondary { border: 1px solid #dfe1da; background: #fff; color: #555b52; }
        .aqm-footer .primary { border: 0; background: #667d42; color: #fff; }
        .aqm-footer button:disabled { opacity: .42; cursor: default; }
        .aqm-complete { display: grid; place-items: center; gap: 10px; padding: 36px 0 10px; color: #5b7042; }
        .aqm-complete button { padding: 9px 14px; border: 0; border-radius: 9px; background: #667d42; color: #fff; font-weight: 800; cursor: pointer; }
        @media (max-width: 640px) { .aqm-modal { padding: 22px; } .aqm-footer { display: grid; grid-template-columns: 1fr 1fr; } .aqm-footer button { width: 100%; } .aqm-reopen { right: 14px; bottom: 14px; } }
      `}</style>
    </>
  );
}
