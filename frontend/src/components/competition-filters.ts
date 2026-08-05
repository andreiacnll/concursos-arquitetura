export type CompetitionFilterItem = {
  titulo?: string | null;
  entidade?: string | null;
  distrito?: string | null;
  municipio?: string | null;
  tipo_procedimento?: string | null;
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

export type DeadlineFilter = "todos" | "7" | "15" | "30";

export type CompetitionFiltersState = {
  district: string;
  precoMin: string;
  precoMax: string;
  entidadeQuery: string;
  prazoFilter: DeadlineFilter;
  selectedProcedures: string[];
  selectedServices: string[];
};

export const DEFAULT_COMPETITION_FILTERS: CompetitionFiltersState = {
  district: "Todos os distritos",
  precoMin: "",
  precoMax: "",
  entidadeQuery: "",
  prazoFilter: "todos",
  selectedProcedures: [],
  selectedServices: [],
};

export const procedureOptions = [
  "Concurso público",
  "Concurso limitado por prévia qualificação",
  "Concurso de conceção",
  "Consulta prévia",
  "Ajuste direto",
];

export const serviceOptions = [
  "Elaboração de projeto",
  "Revisão / Análise de projeto",
  "Concurso de conceção",
  "Fiscalização / Coordenação",
];

export function normalizeText(value?: string | null) {
  return (value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

export function categoryForTitle(title: string) {
  const text = normalizeText(title);

  if (text.includes("escola") || text.includes("educa")) return "Escolas";
  if (text.includes("habita") || text.includes("resid")) return "Habitação";
  if (text.includes("saude") || text.includes("hospital")) return "Saúde";
  if (
    text.includes("praca") ||
    text.includes("largo") ||
    text.includes("rua") ||
    text.includes("espaco publico")
  ) {
    return "Espaço público";
  }
  if (text.includes("jardim") || text.includes("parque") || text.includes("paisag")) {
    return "Paisagismo";
  }
  if (
    text.includes("cultura") ||
    text.includes("teatro") ||
    text.includes("biblioteca") ||
    text.includes("centro cultural")
  ) {
    return "Cultura";
  }
  if (
    text.includes("equipamento publico") ||
    text.includes("equipamento municipal") ||
    text.includes("edificio municipal") ||
    text.includes("servicos municipais")
  ) {
    return "Equipamentos públicos";
  }
  if (
    text.includes("mobilidade") ||
    text.includes("estacao") ||
    text.includes("terminal") ||
    text.includes("metro") ||
    text.includes("ferrovi") ||
    text.includes("ciclovia")
  ) {
    return "Mobilidade";
  }
  if (text.includes("patrim") || text.includes("museu")) return "Património";

  return "Outros";
}

export function matchesProcedure(
  item: CompetitionFilterItem,
  selectedProcedures: string[],
) {
  if (selectedProcedures.length === 0) return true;

  const source = normalizeText(item.tipo_procedimento);

  return selectedProcedures.some((procedure) =>
    source.includes(normalizeText(procedure)),
  );
}

export function serviceForCompetition(item: CompetitionFilterItem) {
  const source = normalizeText(
    [item.titulo, item.tipo_procedimento].filter(Boolean).join(" "),
  );

  if (
    source.includes("fiscalizacao") ||
    source.includes("coordenacao de seguranca") ||
    source.includes("coordenacao")
  ) {
    return "Fiscalização / Coordenação";
  }

  if (
    source.includes("revisao") ||
    source.includes("analise de projeto") ||
    source.includes("verificacao de projeto")
  ) {
    return "Revisão / Análise de projeto";
  }

  if (
    source.includes("concurso de concecao") ||
    source.includes("concurso de concepcao")
  ) {
    return "Concurso de conceção";
  }

  if (
    source.includes("elaboracao de projeto") ||
    source.includes("projeto de arquitetura") ||
    source.includes("projecto de arquitectura") ||
    source.includes("projeto")
  ) {
    return "Elaboração de projeto";
  }

  return null;
}

export function matchesService(
  item: CompetitionFilterItem,
  selectedServices: string[],
) {
  if (selectedServices.length === 0) return true;

  const service = serviceForCompetition(item);
  return service !== null && selectedServices.includes(service);
}

export function hasActiveCompetitionFilters(filters: CompetitionFiltersState) {
  return (
    filters.district !== DEFAULT_COMPETITION_FILTERS.district ||
    filters.precoMin !== "" ||
    filters.precoMax !== "" ||
    filters.entidadeQuery.trim() !== "" ||
    filters.prazoFilter !== "todos" ||
    filters.selectedProcedures.length > 0 ||
    filters.selectedServices.length > 0
  );
}

export function matchesCompetitionFilters(
  item: CompetitionFilterItem,
  filters: CompetitionFiltersState,
) {
  const matchesDistrict =
    filters.district === "Todos os distritos" ||
    item.distrito === filters.district ||
    item.municipio === filters.district;

  return (
    matchesDistrict &&
    matchesProcedure(item, filters.selectedProcedures) &&
    matchesService(item, filters.selectedServices) &&
    matchesAdvancedFilters(item, {
      precoMin: filters.precoMin,
      precoMax: filters.precoMax,
      entidadeQuery: filters.entidadeQuery,
      prazoFilter: filters.prazoFilter,
    })
  );
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
  const hasPriceFilter = min !== null || max !== null;
  const matchesPrice = hasPriceFilter
    ? value !== null &&
      (min === null || value >= min) &&
      (max === null || value <= max)
    : true;

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
