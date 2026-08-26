export type CompetitionDateSource = {
  data_publicacao_iso?: string | null;
  data?: string | null;
  first_seen_at?: string | null;
  data_limite?: string | null;
};

export type CompetitionPublication = {
  label: "Publicado" | "Detetado";
  date: string;
  rawDate: string;
};

function isValidCalendarDate(year: number, month: number, day: number) {
  const date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  );
}

export function formatCompetitionDate(value?: string | null): string | null {
  const input = String(value ?? "").trim();
  if (!input) return null;

  const isoDate = input.match(/^(\d{4})-(\d{2})-(\d{2})(?:$|T)/);
  if (isoDate) {
    const [, year, month, day] = isoDate;
    if (!isValidCalendarDate(Number(year), Number(month), Number(day))) return null;
    return `${day}/${month}/${year}`;
  }

  const localDate = input.match(/^(\d{2})[/-](\d{2})[/-](\d{4})$/);
  if (localDate) {
    const [, day, month, year] = localDate;
    if (!isValidCalendarDate(Number(year), Number(month), Number(day))) return null;
    return `${day}/${month}/${year}`;
  }

  const parsed = new Date(input);
  if (Number.isNaN(parsed.getTime())) return null;

  return new Intl.DateTimeFormat("pt-PT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Europe/Lisbon",
  }).format(parsed);
}

export function getCompetitionPublication(
  competition: CompetitionDateSource,
): CompetitionPublication | null {
  for (const rawDate of [competition.data_publicacao_iso, competition.data]) {
    const date = formatCompetitionDate(rawDate);
    if (date && rawDate) return { label: "Publicado", date, rawDate };
  }

  const date = formatCompetitionDate(competition.first_seen_at);
  if (date && competition.first_seen_at) {
    return { label: "Detetado", date, rawDate: competition.first_seen_at };
  }

  return null;
}