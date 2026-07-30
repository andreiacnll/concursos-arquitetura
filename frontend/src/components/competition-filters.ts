export type CompetitionFilterItem = {
  entidade?: string | null;
  preco_base?: string | number | null;
  valor_procedimento?: string | number | null;
  valor_obra?: string | number | null;
  data_limite?: string | null;
  data_entrega_propostas?: string | null;
  data_fim_calculada?: string | null;
  data_publicacao_iso?: string | null;
  data?: string | null;
};

export type CompetitionSort =
  | "recentes"
  | "antigos"
  | "prazo"
  | "valor_desc"
  | "valor_asc";

function normalizeText(value?: string | null) {
  return (value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

export function parseMonetaryValue(
  value?: string | number | null,
): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (!value) return null;

  let normalized = value.replace(/[^\d,.-]/g, "").trim();
  if (!normalized) return null;

  if (normalized.includes(",")) {
    normalized = normalized.replace(/\./g, "").replace(",", ".");
  } else {
    const dots = normalized.match(/\./g)?.length ?? 0;
    if (dots > 1 || /^-?\d{1,3}(\.\d{3})+$/.test(normalized)) {
      normalized = normalized.replace(/\./g, "");
    }
  }

  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

export function getCompetitionValue(item: CompetitionFilterItem) {
  for (const value of [
    item.valor_obra,
    item.preco_base,
    item.valor_procedimento,
  ]) {
    const parsed = parseMonetaryValue(value);
    if (parsed !== null) return parsed;
  }
  return null;
}

export function getCompetitionPriceRange(
  items: CompetitionFilterItem[],
): { min: number; max: number; count: number } | null {
  const values = items
    .map(getCompetitionValue)
    .filter((value): value is number => value !== null);

  if (values.length === 0) return null;

  return {
    min: Math.min(...values),
    max: Math.max(...values),
    count: values.length,
  };
}

export function parseFilterDate(value?: string | null): Date | null {
  if (!value) return null;
  const clean = String(value).trim();
  const iso = clean.match(/^(\d{4})-(\d{2})-(\d{2})/);
  const pt = clean.match(/^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})/);

  const parts = iso
    ? [Number(iso[1]), Number(iso[2]), Number(iso[3])]
    : pt
      ? [Number(pt[3]), Number(pt[2]), Number(pt[1])]
      : null;
  if (!parts) return null;

  const [year, month, day] = parts;
  const parsed = new Date(year, month - 1, day, 12, 0, 0, 0);
  if (
    parsed.getFullYear() !== year ||
    parsed.getMonth() !== month - 1 ||
    parsed.getDate() !== day
  ) {
    return null;
  }
  return parsed;
}

export function getCompetitionDeadline(item: CompetitionFilterItem) {
  return (
    parseFilterDate(item.data_entrega_propostas) ??
    parseFilterDate(item.data_fim_calculada) ??
    parseFilterDate(item.data_limite)
  );
}

export function matchesAdvancedFilters(
  item: CompetitionFilterItem,
  filters: {
    precoMin: string;
    precoMax: string;
    entidadeQuery: string;
    prazoFilter: "todos" | "7" | "15" | "30";
  },
  today = new Date(),
) {
  const min = parseMonetaryValue(filters.precoMin);
  const max = parseMonetaryValue(filters.precoMax);
  const value = getCompetitionValue(item);
  // Concursos sem valor permanecem visíveis; apenas não participam
  // no cálculo nem na comparação do intervalo.
  const matchesPrice =
    value === null ||
    ((min === null || value >= min) && (max === null || value <= max));

  const entity = normalizeText(filters.entidadeQuery.trim());
  const matchesEntity =
    !entity || normalizeText(item.entidade).includes(entity);

  let matchesDeadline = true;
  if (filters.prazoFilter !== "todos") {
    const deadline = getCompetitionDeadline(item);
    const firstDay = new Date(today);
    firstDay.setHours(0, 0, 0, 0);
    const lastDay = new Date(firstDay);
    lastDay.setDate(lastDay.getDate() + Number(filters.prazoFilter));
    lastDay.setHours(23, 59, 59, 999);
    matchesDeadline =
      deadline !== null && deadline >= firstDay && deadline <= lastDay;
  }

  return matchesPrice && matchesEntity && matchesDeadline;
}

export function compareCompetitions(
  a: CompetitionFilterItem,
  b: CompetitionFilterItem,
  sort: CompetitionSort,
) {
  if (sort === "prazo") {
    const aTime = getCompetitionDeadline(a)?.getTime();
    const bTime = getCompetitionDeadline(b)?.getTime();
    if (aTime === undefined) return bTime === undefined ? 0 : 1;
    if (bTime === undefined) return -1;
    return aTime - bTime;
  }

  if (sort === "valor_asc" || sort === "valor_desc") {
    const aValue = getCompetitionValue(a);
    const bValue = getCompetitionValue(b);
    if (aValue === null) return bValue === null ? 0 : 1;
    if (bValue === null) return -1;
    return sort === "valor_asc" ? aValue - bValue : bValue - aValue;
  }

  const aTime = parseFilterDate(a.data_publicacao_iso ?? a.data)?.getTime() ?? 0;
  const bTime = parseFilterDate(b.data_publicacao_iso ?? b.data)?.getTime() ?? 0;
  return sort === "antigos" ? aTime - bTime : bTime - aTime;
}
