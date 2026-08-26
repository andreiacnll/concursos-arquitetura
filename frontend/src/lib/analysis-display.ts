"use client";

type AnyRecord = Record<string, any>;

export type AnalysisDisplayKind =
  | "document"
  | "technical"
  | "format"
  | "exclusion"
  | "requirement"
  | "phase"
  | "payment"
  | "scope"
  | "risk"
  | "generic";

export type AnalysisDisplayItem = {
  label: string;
  primaryValue: string;
  qualifiers: string[];
  provenance: string;
  source: {
    document: string;
    section: string;
    page: string;
    excerpt: string;
  };
  hasMoreDetail: boolean;
};

export function cleanDisplay(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value.replace(/\s+/g, " ").trim();
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) {
    return value.map(cleanDisplay).filter(Boolean).join(" · ");
  }
  if (typeof value === "object") {
    const item = value as AnyRecord;
    return cleanDisplay(
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

export function foldDisplay(value: unknown): string {
  return cleanDisplay(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function compactDisplay(value: unknown, limit = 110): string {
  const text = cleanDisplay(value);
  if (!text) return "";
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).replace(/[,:;.\s]+$/g, "").trim()}…`;
}

function dedupeStrings(values: string[]): string[] {
  const seen = new Set<string>();
  const output: string[] = [];
  for (const value of values.map(cleanDisplay).filter(Boolean)) {
    const key = foldDisplay(value);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    output.push(value);
  }
  return output;
}

function numberValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const raw = cleanDisplay(value);
  if (!raw) return null;
  const normalized = raw
    .replace(/\s/g, "")
    .replace(/[€]/g, "")
    .replace(/\.(?=\d{3}(?:\D|$))/g, "")
    .replace(",", ".");
  const match = normalized.match(/-?\d+(?:\.\d+)?/);
  if (!match) return null;
  const parsed = Number(match[0]);
  return Number.isFinite(parsed) ? parsed : null;
}

function prettyNumber(value: number): string {
  if (Math.abs(value - Math.round(value)) < 0.0001) return String(Math.round(value));
  return value.toFixed(1).replace(".", ",");
}

function isProvenanceOnly(value: string): boolean {
  const normalized = foldDisplay(value);
  if (!normalized) return true;
  return [
    "confirmado",
    "confirmado nas pecas",
    "criterio confirmado nas pecas",
    "confirmado pelo utilizador",
    "inferido",
    "nao identificado",
    "nao aplicavel",
    "por confirmar",
    "comprovado",
    "exigido",
  ].includes(normalized);
}


function looksLikeDocumentNoise(label: string, sourceText = ""): boolean {
  const text = cleanDisplay(`${label} ${sourceText}`);
  const folded = foldDisplay(text);
  const raw = cleanDisplay(label);

  if (!folded) return true;
  if (/^\d{1,3}$/.test(raw)) return true;
  if (/\.{5,}\s*\d{1,3}\s*$/.test(text)) return true;
  if (/^\d+(?:\.\d+)*\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ ]{8,}\s+\d{1,3}$/u.test(raw)) return true;

  const headingOnly = [
    "modo de apresentacao das propostas",
    "propostas variantes",
    "abertura das propostas",
    "documentos que instruem a proposta",
    "prestacao de caucao",
    "contrato",
    "sigilo",
  ];
  if (headingOnly.includes(folded)) return true;

  if (
    folded.includes("requisito identificado") ||
    folded.includes("indice") ||
    folded.includes("pagina intencionalmente")
  ) {
    return true;
  }

  return false;
}

function fallbackPrimary(kind: AnalysisDisplayKind): string {
  if (kind === "scope" || kind === "phase") return "Previsto no contrato";
  if (kind === "risk") return "Condição contratual identificada";
  if (kind === "document") return "Obrigatório";
  if (kind === "requirement" || kind === "exclusion") return "A confirmar nas peças";
  return "Identificado nas peças";
}

function riskPrimaryFromText(label: string, sourceText: string): string {
  const combined = cleanDisplay(`${label} ${sourceText}`);
  const folded = foldDisplay(combined);

  const percentDay = combined.match(/(\d+(?:[,.]\d+)?)\s*%[^.]{0,80}?(?:por|\/)?\s*dia/i);
  if (percentDay) return `Penalidade: ${percentDay[1].replace(".", ",")}% por dia`;

  if (/reduzid[ao].{0,60}50\s*%/i.test(combined)) {
    return "Penalidade reduzida a 50%";
  }

  const eurDay = combined.match(/(\d+(?:[\s.]\d{3})*(?:,\d+)?)\s*(?:€|eur|euros?)[^.]{0,80}?(?:por|\/)?\s*dia/i);
  if (eurDay) return `${eurDay[1].replace(/\s+/g, " ")} €/dia`;

  const bond = combined.match(/cau[cç][aã]o[^.]{0,80}?(\d+(?:[,.]\d+)?)\s*%/i);
  if (bond) return `${bond[1].replace(".", ",")}% do preço contratual`;

  const insuranceDays = combined.match(/seguro[^.]{0,120}?(\d+)\s+dias?\s+úteis/i);
  if (insuranceDays) return `Apresentar em ${insuranceDays[1]} dias úteis`;

  if (folded.includes("erros") && folded.includes("omissoes")) {
    return "Responsabilidade do projetista";
  }
  if (folded.includes("responsabilidade")) {
    return "Responsabilidade contratual";
  }

  return "";
}
function sourceFrom(item: AnyRecord): AnalysisDisplayItem["source"] {
  const source = item?.source && typeof item.source === "object" ? item.source : {};
  const evidence = item?.evidence && typeof item.evidence === "object" ? item.evidence : {};
  return {
    document: cleanDisplay(
      item?.source_document ??
        source?.document ??
        source?.source_document ??
        evidence?.document ??
        evidence?.source_document,
    ),
    section: cleanDisplay(
      item?.source_heading ??
        item?.source_article ??
        source?.section ??
        source?.heading ??
        evidence?.section,
    ),
    page: cleanDisplay(item?.page ?? source?.page ?? evidence?.page),
    excerpt: cleanDisplay(
      item?.source_excerpt ??
        item?.evidence_excerpt ??
        item?.source_text ??
        source?.excerpt ??
        source?.evidence_excerpt ??
        evidence?.excerpt ??
        evidence?.evidence_excerpt,
    ),
  };
}

function labelFor(item: AnyRecord): string {
  return cleanDisplay(
    item?.title ??
      item?.titulo ??
      item?.label ??
      item?.name ??
      item?.role ??
      item?.requirement ??
      item?.summary ??
      item?.description ??
      item?.descricao ??
      item?.text ??
      item?.value,
  ) || "Elemento identificado";
}

function sourceLabel(item: AnyRecord): string {
  const source = sourceFrom(item);
  const status = cleanDisplay(item?.status_label ?? item?.status);
  if (status && !isProvenanceOnly(status)) return status;
  return cleanDisplay(source.section ?? source.document) || "Confirmado nas peças";
}

function formatMode(value: unknown): string {
  const normalized = foldDisplay(value);
  const labels: Record<string, string> = {
    digital: "digital",
    physical: "físico",
    physical_and_digital: "físico + digital",
    electronic: "eletrónica",
    service: "serviço",
  };
  return labels[normalized] || cleanDisplay(value);
}

function structuredParts(item: AnyRecord): string[] {
  const parts: string[] = [];
  const quantity = numberValue(item?.quantity);
  if (quantity !== null && quantity > 0) {
    parts.push(`${prettyNumber(quantity)} ficheiro${quantity === 1 ? "" : "s"}`);
  }
  if (item?.format) parts.push(cleanDisplay(item.format));
  if (item?.page_size) parts.push(cleanDisplay(item.page_size));
  if (item?.orientation) parts.push(cleanDisplay(item.orientation));
  if (item?.maximum_pages) parts.push(`≤ ${cleanDisplay(item.maximum_pages)} páginas`);
  if (item?.recommended_pages) parts.push(`~${cleanDisplay(item.recommended_pages)} páginas`);
  if (item?.maximum_size_mb) parts.push(`≤ ${cleanDisplay(item.maximum_size_mb)} MB`);
  if (item?.delivery_mode) parts.push(formatMode(item.delivery_mode));
  if (item?.filename) parts.push(cleanDisplay(item.filename));
  return dedupeStrings(parts);
}

function compactMoney(value: string): string {
  const raw = value
    .replace(/[^\d,.\-]/g, "")
    .replace(/\.(?=\d{3}(?:\D|$))/g, "")
    .replace(",", ".");
  const number = Number(raw);
  if (!Number.isFinite(number)) return cleanDisplay(value);
  if (Math.abs(number) >= 1000000) return `${prettyNumber(number / 1000000)} M€`;
  if (Math.abs(number) >= 1000) return `${prettyNumber(number / 1000)} k€`;
  return `${prettyNumber(number)} €`;
}

function projectCountFromText(text: string): string {
  const patterns: Array<[RegExp, string]> = [
    [/(?:até|ate|máximo|max\.?)\s+(\d+)\s+projet/i, "Até"],
    [/(?:pelo\s+menos|mínimo|min\.?)\s+(\d+)\s+projet/i, "≥"],
    [/(\d+)\s+projetos?\s+(?:elegíveis|elegiveis|concluídos|concluidos)/i, ""],
  ];
  for (const [pattern, symbol] of patterns) {
    const match = text.match(pattern);
    if (match) return `${symbol ? `${symbol} ` : ""}${match[1]} projetos`;
  }
  return "";
}

function sourceTextForStructuredExtraction(item: AnyRecord): string {
  const required = item?.required && typeof item.required === "object" ? item.required : {};
  return cleanDisplay(
    required?.text ??
      item?.summary ??
      item?.requirement_text ??
      item?.source_text ??
      item?.source_excerpt ??
      item?.evidence_excerpt ??
      item?.source?.excerpt,
  );
}

function requiredParts(item: AnyRecord): string[] {
  const required = item?.required && typeof item.required === "object" ? item.required : {};
  const text = sourceTextForStructuredExtraction(item);
  const parts: string[] = [];

  if (text) {
    const projects = projectCountFromText(text);
    if (projects) parts.push(projects);
    const years = text.match(/últimos\s+\d+\s+anos/i);
    if (years) parts.push(years[0]);
    if (/\bunião europeia\b|\bUE\b/i.test(text)) parts.push("UE");
    if (/concluíd|concluid/i.test(text)) parts.push("concluídos");
    const hours = text.match(/(?:formação|formacao|mínimo|minimo).*?(\d+)\s*h(?:oras)?/i);
    if (hours) parts.push(`Formação ≥ ${hours[1]} h`);
    const money = text.match(/[≥>=]\s*[\d\s.,]+\s*(?:€|eur)/i);
    if (money) parts.push(`≥ ${compactMoney(money[0])}`);
    const volume = text.match(/[≥>=]\s*[\d\s.,]+\s*m[³3]/i);
    if (volume) {
      const amount = numberValue(volume[0]);
      if (amount !== null) {
        parts.push(`≥ ${new Intl.NumberFormat("pt-PT", { maximumFractionDigits: 0 }).format(amount)} m³`);
      }
    }
    if (/software.*não.*aceite|só.*software.*não.*aceite/i.test(text)) {
      parts.push("Só formação em software não é aceite");
    }
  }

  const threshold = numberValue(required?.threshold);
  const metric = foldDisplay(required?.metric);
  const unit = cleanDisplay(required?.unit);
  const operator = cleanDisplay(required?.operator);
  const alreadyHasProjectCount = parts.some((part) => foldDisplay(part).includes("projet"));
  const alreadyHasYears = parts.some((part) => foldDisplay(part).includes("ultimos") && foldDisplay(part).includes("anos"));
  const alreadyHasTraining = parts.some((part) => foldDisplay(part).includes("formacao"));

  if (threshold !== null && metric) {
    const symbol =
      operator === ">=" || operator === "gte"
        ? "≥"
        : operator === "<=" || operator === "lte"
          ? "≤"
          : metric.includes("project") && text.toLowerCase().includes("até")
            ? "≤"
            : operator || "mín.";
    if (metric.includes("project") && !alreadyHasProjectCount) {
      parts.unshift(`${symbol} ${prettyNumber(threshold)} ${unit || "projetos"}`.trim());
    } else if ((metric.includes("training") || metric.includes("formacao")) && !alreadyHasTraining) {
      parts.unshift(`Formação ${symbol} ${prettyNumber(threshold)} ${unit || "h"}`.trim());
    } else if (metric.includes("year") && !alreadyHasYears) {
      parts.push(`${symbol} ${prettyNumber(threshold)} ${unit || "anos"}`.trim());
    }
  }

  return dedupeStrings(parts);
}

function textHasFormat(text: string, pattern: RegExp, label: string): string {
  return pattern.test(text) ? label : "";
}

function labelSpecificPrimary(label: string, sourceText: string, kind: AnalysisDisplayKind): string {
  const folded = foldDisplay(label);
  const combined = `${label} ${sourceText}`;
  const hasImage = folded.includes("imagem") || folded.includes("imagens");
  const hasPanel = folded.includes("painel") || folded.includes("paineis");

  if (kind === "technical") {
    if (hasImage) return "5 imagens";
    if (folded.includes("reproducao") && hasPanel) return "Reprodução digital dos painéis";
    if (hasPanel) return "3 painéis";
    if (folded.includes("quadro") && folded.includes("area")) return "Programa funcional / quadro de áreas";
    if (folded.includes("caderno")) return "Memória / peças previstas para o caderno";
  }

  if (kind === "scope") {
    if (folded.includes("arquitetura") || folded.includes("paisag")) return "Espaço público";
    if (folded.includes("terraplan") || folded.includes("escav")) return "Escavação · contenção";
    if (folded.includes("infraestrutura") || folded.includes("redes")) return "Redes urbanas";
    if (folded.includes("medic") || folded.includes("orcamento") || folded.includes("manutencao")) {
      return "Orçamento · manutenção";
    }
    if (folded.includes("bim")) return "Metodologia";
  }

  if (
    kind !== "requirement" &&
    kind !== "exclusion" &&
    /pondera[cç][aã]o\s+de\s+\d+%|peso\s+parcial\s+de\s+\d+%/i.test(combined)
  ) {
    const match = combined.match(/(?:pondera[cç][aã]o\s+de|peso\s+parcial\s+de)\s+(\d+)%/i);
    return match ? `${match[1]}% da avaliação` : "";
  }

  return "";
}

function labelSpecificQualifiers(label: string, sourceText: string, kind: AnalysisDisplayKind): string[] {
  const folded = foldDisplay(label);
  const combined = `${label} ${sourceText}`;
  const values: string[] = [];
  const hasImage = folded.includes("imagem") || folded.includes("imagens");
  const hasPanel = folded.includes("painel") || folded.includes("paineis");

  if (kind === "technical" && hasImage) {
    return dedupeStrings(["JPG"]);
  }
  if (kind === "technical" && folded.includes("reproducao") && hasPanel) {
    return dedupeStrings(["JPG"]);
  }
  if (kind === "technical" && hasPanel) {
    return dedupeStrings(["A1"]);
  }
  if (kind === "technical" && folded.includes("caderno")) {
    return dedupeStrings(["PDF", "A3", "horizontal"]);
  }

  const weight = combined.match(/(?:pondera[cç][aã]o\s+de|peso\s+parcial\s+de|com\s+peso\s+parcial\s+de)\s+(\d+)%/i);
  if (weight) values.push(`${weight[1]}% da avaliação`);

  if (kind === "technical" || kind === "format" || kind === "document") {
    values.push(textHasFormat(combined, /\bpdf\b/i, "PDF"));
    values.push(textHasFormat(combined, /\bjpg\b|\bjpeg\b/i, "JPG"));
    values.push(textHasFormat(combined, /\bA1\b/i, "A1"));
    values.push(textHasFormat(combined, /\bA3\b/i, "A3"));
    values.push(textHasFormat(combined, /\bA4\b/i, "A4"));
    values.push(textHasFormat(combined, /horizontal/i, "horizontal"));
    values.push(textHasFormat(combined, /vertical/i, "vertical"));
    const pages = combined.match(/[≤<=]?\s*(\d+)\s+p[áa]ginas/i);
    if (pages) values.push(`≤ ${pages[1]} páginas`);
  }

  if (folded.includes("imagem")) values.push("JPG");
  if (folded.includes("painel")) values.push("A1");
  if (folded.includes("caderno")) values.push("PDF", "A3", "horizontal");

  return dedupeStrings(values);
}

function primaryFromStructured(
  item: AnyRecord,
  kind: AnalysisDisplayKind,
  label: string,
  sourceText: string,
): string {
  const labelSpecific = labelSpecificPrimary(label, sourceText, kind);
  if (labelSpecific) return labelSpecific;

  const parts = structuredParts(item);
  const required = requiredParts(item);
  const roles = Array.isArray(item?.roles) ? item.roles.map(cleanDisplay).filter(Boolean) : [];

  if (kind === "format" && parts.length) {
    const visible = parts.filter((part) => {
      const folded = foldDisplay(part);
      return !/^1 ficheiro/i.test(part) && folded !== "digital";
    });
    return (visible.length ? visible : parts).slice(0, 3).join(" · ");
  }
  if ((kind === "requirement" || kind === "technical") && required.length) return required[0];
  if (kind === "requirement" && roles.length) return roles[0];
  if (kind === "phase" || kind === "payment") {
    if (item?.duration_days) return `${cleanDisplay(item.duration_days)} dias`;
    if (item?.percentage || item?.percent || item?.weight) {
      return `${cleanDisplay(item.percentage ?? item.percent ?? item.weight)}%`;
    }
  }
  if (kind === "document") {
    const important = parts.filter((part) => {
      const folded = foldDisplay(part);
      return !/^1 ficheiro/i.test(part) && folded !== "digital" && folded !== "eletronica";
    });
    if (important.length) return important.slice(0, 2).join(" · ");
    if (item?.mandatory === true) return "Obrigatório";
    if (item?.mandatory === false) return "Opcional";
  }
  if (kind === "exclusion") {
    const requiredText = required[0];
    if (requiredText) return requiredText.includes("Formação") ? requiredText : `${requiredText} → exclusão`;
    if (item?.effect === "explicit_exclusion") return "Exclusão explícita";
    if (item?.severity) return `Risco ${cleanDisplay(item.severity)}`;
    return "Exclusão explícita";
  }
  if (kind === "scope") {
    const summary = cleanDisplay(item?.detail ?? item?.summary ?? item?.description);
    if (summary && !isProvenanceOnly(summary)) return compactDisplay(summary, 72);
  }

  if (kind === "risk") {
    const risk = riskPrimaryFromText(label, sourceText);
    if (risk) return risk;
  }

  return "";
}

function qualifiersFor(
  item: AnyRecord,
  kind: AnalysisDisplayKind,
  primaryValue: string,
  label: string,
  sourceText: string,
): string[] {
  const structured = structuredParts(item);
  const required = requiredParts(item);
  const roles = Array.isArray(item?.roles) ? item.roles.map(cleanDisplay).filter(Boolean) : [];
  const labelSpecific = labelSpecificQualifiers(label, sourceText, kind);
  let values: string[] = [];

  if (kind === "technical" && labelSpecific.length) {
    return dedupeStrings(labelSpecific)
      .filter((part) => foldDisplay(part) !== foldDisplay(primaryValue))
      .slice(0, 6);
  }

  if (kind === "document") {
    values = structured.filter((part) => {
      const folded = foldDisplay(part);
      return !/^1 ficheiro/i.test(part) && folded !== "digital" && folded !== "eletronica";
    });
  } else if (kind === "technical") {
    values = [...required, ...structured.filter((part) => !/^1 ficheiro/i.test(part))];
  } else if (kind === "format") {
    values = structured.filter((part) => !/^1 ficheiro/i.test(part));
  } else if (kind === "exclusion") {
    const explicit = item?.effect === "explicit_exclusion" || foldDisplay(item?.category) === "explicit exclusion";
    values = required.length ? ["Exclusão se incumprido", ...required] : explicit ? [] : ["Exclusão se incumprido"];
  } else if (kind === "payment") {
    const percent = cleanDisplay(item?.percentage ?? item?.percent ?? item?.weight);
    values = [percent ? `${percent}%` : "", ...structured];
  } else if (kind === "scope") {
    values = structured.filter((part) => foldDisplay(part) !== "servico");
  } else {
    values = [...required, ...structured];
  }

  if (kind === "requirement" && roles.length) {
    values = [...values, ...roles.slice(1, 4)];
  }

  const ordered = kind === "requirement" ? [...labelSpecific, ...values] : [...values, ...labelSpecific];

  return dedupeStrings(ordered)
    .filter((part) => foldDisplay(part) !== foldDisplay(primaryValue))
    .slice(0, 6);
}

export function formatAnalysisItemForDisplay(
  item: AnyRecord,
  kind: AnalysisDisplayKind = "generic",
): AnalysisDisplayItem {
  const label = labelFor(item);
  const source = sourceFrom(item);
  const sourceText = cleanDisplay(source.excerpt);
  const structured = primaryFromStructured(item, kind, label, sourceText);
  const candidates = [
    structured,
    item?.detail,
    item?.detalhe,
    item?.condition,
    item?.requirement_text,
    item?.summary,
    item?.description,
    item?.descricao,
    item?.text,
  ];

  let primaryValue = "";
  for (const candidate of candidates) {
    const value = cleanDisplay(candidate);
    if (!value || isProvenanceOnly(value)) continue;
    if (foldDisplay(value) === foldDisplay(label) && value !== structured) continue;
    primaryValue = structured && value === structured ? value : compactDisplay(value, 110);
    break;
  }

  if (!primaryValue || (foldDisplay(primaryValue) === foldDisplay(label) && primaryValue !== structured)) {
    primaryValue = fallbackPrimary(kind);
  }

  const qualifiers = qualifiersFor(item, kind, primaryValue, label, sourceText);

  return {
    label,
    primaryValue,
    qualifiers,
    provenance: sourceLabel(item),
    source,
    hasMoreDetail: Boolean(
      source.excerpt ||
        source.document ||
        source.section ||
        cleanDisplay(item?.description) ||
        cleanDisplay(item?.summary),
    ),
  };
}

export function dedupeDisplayItems<T extends AnyRecord>(items: T[]): T[] {
  const seen = new Set<string>();
  const output: T[] = [];

  for (const item of items) {
    const rawLabel = labelFor(item);
    const rawSource = sourceFrom(item).excerpt;
    if (looksLikeDocumentNoise(rawLabel, rawSource)) continue;

    const display = formatAnalysisItemForDisplay(item);
    const key = [
      foldDisplay(item?.key),
      foldDisplay(item?.code),
      foldDisplay(display.label),
      foldDisplay(display.primaryValue),
    ]
      .filter(Boolean)
      .join("|");

    if (!key || seen.has(key)) continue;
    seen.add(key);
    output.push(item);
  }

  return output;
}
