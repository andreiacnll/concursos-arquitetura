export type CompetitionAwardCriteriaSource = {
  criterio_tipo?: string | null;
  criterio_resumo?: string | null;
  criterio_detalhe?: string | null;
  criterio_fatores?: string | null;
  criterio_estado?: string | null;
};

export type CompetitionAwardFactor = {
  name: string;
  weight: number;
  type: "qualidade" | "preco" | "outro";
};

export type CompetitionAwardCriteria = {
  primary: string;
  secondary: string | null;
  factors: CompetitionAwardFactor[];
  weightTotal: number | null;
  weightDiagnostic: string | null;
  confirmed: boolean;
};

const text = (value?: string | null) => String(value ?? "").trim() || null;

function factorType(name: string): CompetitionAwardFactor["type"] {
  const normalized = name.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  if (normalized.includes("preco")) return "preco";
  if (normalized.includes("qualidade")) return "qualidade";
  return "outro";
}

function cleanName(value: string) {
  return value.replace(/^(?:outros?\s+)?outro\s+nome\s*:\s*/i, "").replace(/\s*:\s*$/, "").trim();
}

function parseFactors(value?: string | null): CompetitionAwardFactor[] {
  const raw = text(value);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.flatMap((item) => {
        const name = cleanName(String(item?.nome ?? item?.name ?? ""));
        const weight = Number(String(item?.peso ?? item?.weight ?? "").replace(",", "."));
        return name && Number.isFinite(weight) ? [{ name, weight, type: factorType(name) }] : [];
      });
    }
  } catch { /* Text format is also supported for historical rows. */ }
  return raw.split(/\n|\s*[\u2022\u00b7]\s*|\s+\ufffd\s+/).flatMap((line) => {
    const match = line.trim().match(/^(.*?)(?:\s*:?)\s*(\d+(?:[,.]\d+)?)\s*%\s*$/);
    if (!match) return [];
    const name = cleanName(match[1]);
    const weight = Number(match[2].replace(",", "."));
    return name && Number.isFinite(weight) ? [{ name, weight, type: factorType(name) }] : [];
  });
}

function legalSummary(value?: string | null) {
  const raw = text(value);
  if (!raw) return null;
  const normalized = raw.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  if (normalized.includes("melhor relacao qualidade-preco") || (normalized.includes("melhor rela") && normalized.includes("qualidade") && normalized.includes("pre"))) return "Melhor rela\u00e7\u00e3o qualidade-pre\u00e7o";
  if (normalized.includes("proposta economicamente mais vantajosa")) return "Proposta economicamente mais vantajosa";
  return null;
}

export function getCompetitionAwardCriteria(competition: CompetitionAwardCriteriaSource): CompetitionAwardCriteria {
  const summary = text(competition.criterio_resumo);
  const type = text(competition.criterio_tipo);
  const detail = text(competition.criterio_detalhe);
  const factors = parseFactors(competition.criterio_fatores).length
    ? parseFactors(competition.criterio_fatores)
    : parseFactors(summary) || parseFactors(detail);
  const factorList = factors.length >= 2 ? factors : [];
  const weightTotal = factorList.length ? factorList.reduce((total, factor) => total + factor.weight, 0) : null;
  const weightDiagnostic = weightTotal !== null && weightTotal !== 100 ? `Pondera\u00e7\u00f5es somam ${weightTotal}% (por confirmar)` : null;
  const primary = (factorList.length ? type : summary) || type || legalSummary(summary) || legalSummary(detail) || summary || detail;
  if (!primary) return { primary: competition.criterio_estado === "por_confirmar" ? "Por confirmar" : "Em valida\u00e7\u00e3o documental", secondary: null, factors: [], weightTotal: null, weightDiagnostic: null, confirmed: false };
  return { primary, secondary: type && type !== primary ? (weightDiagnostic ? `${type} \u00b7 ${weightDiagnostic}` : type) : weightDiagnostic, factors: factorList, weightTotal, weightDiagnostic, confirmed: true };
}