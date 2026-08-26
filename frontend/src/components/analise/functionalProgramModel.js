export const EMPTY = "Por confirmar";

export function cleanText(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value.replace(/\s+/g, " ").trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (Array.isArray(value)) {
    return value.map(cleanText).filter(Boolean).join(" · ");
  }
  if (typeof value === "object") {
    const obj = value;
    return cleanText(
      obj.value ??
        obj.normalized_value ??
        obj.text ??
        obj.label ??
        obj.name ??
        obj.description ??
        obj.summary ??
        "",
    );
  }
  return "";
}

export function compactText(value, limit = 140) {
  const text = cleanText(value);
  if (!text) return "";
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).trim()}…`;
}

export function isMeaningful(value) {
  const text = cleanText(value);
  if (!text) return false;
  const normalized = text.toLowerCase();
  return !(
    normalized === "0" ||
    normalized === "0.0" ||
    normalized.includes("not found") ||
    normalized.includes("não identificado") ||
    normalized.includes("nao identificado") ||
    normalized === EMPTY.toLowerCase()
  );
}

export function splitList(value) {
  const text = cleanText(value);
  if (!text) return [];
  return text
    .split(/\s*[·;|]\s*|\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function normalizeList(value, max = 6) {
  const seen = new Set();
  const output = [];
  for (const item of Array.isArray(value) ? value : splitList(value)) {
    const text = compactText(item, 160);
    const signature = text.toLowerCase();
    if (!text || seen.has(signature)) continue;
    seen.add(signature);
    output.push(text);
    if (output.length >= max) break;
  }
  return output;
}

function pickValue(values) {
  for (const value of values) {
    if (isMeaningful(value)) return cleanText(value);
  }
  return "";
}

function normalizeProgramItems(value, max = 8) {
  const items = Array.isArray(value) ? value : splitList(value);
  const seen = new Set();
  const output = [];

  for (const item of items) {
    const label = cleanText(
      item && typeof item === "object"
        ? item.label ?? item.title ?? item.name ?? ""
        : "",
    );
    const rawValue = cleanText(
      item && typeof item === "object"
        ? item.value ?? item.normalized_value ?? item.text ?? ""
        : item,
    );
    const normalizedLabel = label
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "")
      .toLowerCase()
      .trim();

    if (
      !rawValue ||
      ["m", "m2", "area", "area 1", "area 2", "total"].includes(
        normalizedLabel,
      )
    ) {
      continue;
    }

    const text = compactText(
      label && rawValue ? `${label} — ${rawValue}` : rawValue,
      180,
    );
    const signature = text.toLowerCase();
    if (!text || seen.has(signature)) continue;
    seen.add(signature);
    output.push(text);
    if (output.length >= max) break;
  }

  return output;
}

function formatAreaNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  return `${new Intl.NumberFormat("pt-PT", {
    minimumFractionDigits: Number.isInteger(number) ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(number)} m²`;
}

function buildAreaRows(source, legacyProgram) {
  const scheduleRows = source?.area_schedule?.rows;
  const fallback = source?.areas || legacyProgram?.areas || [];
  const rows = Array.isArray(scheduleRows) && scheduleRows.length
    ? scheduleRows
    : fallback;

  const seen = new Set();
  return rows
    .filter((item) => item && typeof item === "object")
    .filter((item) => !item.kind || item.kind === "functional_area")
    .map((item) => {
      const label = cleanText(item.label ?? item.name ?? "");
      const quantity = Number.isFinite(Number(item.quantity))
        ? Number(item.quantity)
        : null;
      const unitArea = Number.isFinite(Number(item.unit_area_m2))
        ? Number(item.unit_area_m2)
        : null;
      const totalArea = Number.isFinite(Number(item.total_area_m2))
        ? Number(item.total_area_m2)
        : null;
      const signature = `${label.toLowerCase()}-${quantity}-${unitArea}-${totalArea}`;
      if (!label || seen.has(signature)) return null;
      seen.add(signature);
      return {
        label,
        quantity,
        quantityLabel: quantity ? String(quantity) : "—",
        unitArea,
        unitAreaLabel: formatAreaNumber(unitArea) || "—",
        totalArea,
        totalAreaLabel:
          formatAreaNumber(totalArea) ||
          cleanText(item.value) ||
          "Por confirmar",
        functionalGroup: cleanText(item.functional_group) || "Outros espaços",
        sourceDocument: cleanText(item.source_document),
        page: Number.isFinite(Number(item.page)) ? Number(item.page) : null,
        sheet: cleanText(item.sheet),
        reconstructionMethod: cleanText(item.reconstruction_method),
        confidence: item.confidence,
      };
    })
    .filter(Boolean);
}

function buildMetric(label, values) {
  const value = pickValue(values);
  return {
    label,
    value: value || EMPTY,
    confirmed: Boolean(value),
  };
}

export function buildFunctionalProgramViewModel({
  functionalProgram = {},
  extraction = {},
} = {}) {
  const facts = extraction?.facts || {};
  const legacyProgram = extraction?.program_functional || {};
  const source =
    functionalProgram && Object.keys(functionalProgram).length
      ? functionalProgram
      : legacyProgram;

  const summary =
    compactText(
      pickValue([
        source.summary,
        source.sintese,
        source.resumo,
        facts.program_summary?.value,
      ]),
      900,
    ) || EMPTY;

  const interventionType =
    compactText(
      pickValue([
        source.intervention_type,
        source.tipo_intervencao,
        facts.intervention_type?.value,
      ]),
      90,
    ) || EMPTY;

  const hasStructuredProgram = Boolean(
    functionalProgram && Object.keys(functionalProgram).length,
  );
  const structuredOrLegacy = (structuredValues, legacyValues) =>
    hasStructuredProgram ? structuredValues : [...structuredValues, ...legacyValues];

  const areaTotal = buildMetric("Área total", structuredOrLegacy([
    source.area_total?.value,
    source.total_area,
  ], [facts.area_total?.value, facts.total_area?.value]));
  const areaBruta = buildMetric("Área bruta", structuredOrLegacy([
    source.area_bruta?.value,
  ], [facts.area_bruta?.value]));
  const areaIntervencao = buildMetric("Área de intervenção", structuredOrLegacy([
    source.area_intervencao?.value,
  ], [facts.area_intervencao?.value]));
  const areaUtil = buildMetric("Área útil total", structuredOrLegacy([
    source.area_util?.value,
  ], [facts.area_util?.value]));

  const areaRows = buildAreaRows(source, legacyProgram);
  const calculatedTotal = Number(source?.area_schedule?.calculated_total_m2);
  const calculatedTotalLabel = Number.isFinite(calculatedTotal)
    ? formatAreaNumber(calculatedTotal)
    : "";

  const previewSections = [
    {
      key: "areas",
      title: "Mapa de áreas",
      items: areaRows.slice(0, 4).map((row) =>
        row.quantity
          ? `${row.label} — ${row.quantity} × ${row.unitAreaLabel} = ${row.totalAreaLabel}`
          : `${row.label} — ${row.totalAreaLabel}`,
      ),
      empty: EMPTY,
    },
    {
      key: "spaces",
      title: "Espaços e funções",
      items: normalizeList(source.main_spaces || source.espacos_principais, 4),
      empty: EMPTY,
    },
    {
      key: "requirements",
      title: "Requisitos programáticos",
      items: normalizeList(source.requirements || source.requisitos, 4),
      empty: EMPTY,
    },
    {
      key: "constraints",
      title: "Condicionantes",
      items: normalizeList(source.constraints || source.condicionantes, 4),
      empty: EMPTY,
    },
  ];

  const modalSections = [
    {
      key: "global-areas",
      title: "Métricas globais confirmadas",
      items: [areaTotal, areaBruta, areaIntervencao, areaUtil],
    },
    {
      key: "area-schedule",
      title: "Mapa de áreas",
      items: areaRows,
      calculatedTotalLabel,
    },
    {
      key: "spaces",
      title: "Espaços e funções",
      items: normalizeList(source.main_spaces || source.espacos_principais, 20),
    },
    {
      key: "requirements",
      title: "Requisitos programáticos",
      items: normalizeList(source.requirements || source.requisitos, 20),
    },
    {
      key: "constraints",
      title: "Condicionantes",
      items: normalizeList(source.constraints || source.condicionantes, 20),
    },
    {
      key: "sources",
      title: "Origem documental",
      items: normalizeList(source?.area_schedule?.source_documents || [], 20),
    },
    {
      key: "warnings",
      title: "Avisos de reconstrução",
      items: normalizeList(
        source?.area_schedule?.warnings || source?.warnings || [],
        20,
      ),
    },
  ];

  return {
    summary,
    interventionType,
    metrics: [areaTotal, areaBruta, areaIntervencao, areaUtil],
    areaRows,
    calculatedTotalLabel,
    previewSections,
    modalSections,
  };
}
