import CompetitionsDashboard from "@/components/CompetitionsDashboard";
import PublicLayout from "@/components/layout/PublicLayout";
import type { Concurso } from "@/components/competition-types";
import { API_URL } from "@/lib/api";

export const dynamic = "force-dynamic";

async function getConcursos(): Promise<Concurso[]> {
  try {
    const response = await fetch(
      `${API_URL}/concursos?estado=todos&apenas_relevantes=true&limite=100`,
      { cache: "no-store" },
    );

    if (!response.ok) {
      throw new Error(`A API respondeu com o estado ${response.status}`);
    }

    const data = await response.json();

    if (Array.isArray(data)) return data;
    if (Array.isArray(data.resultados)) return data.resultados;

    return [];
  } catch (error) {
    console.error("Erro ao carregar concursos:", error);
    return [];
  }
}

export default async function Home() {
  const concursos = await getConcursos();

  return (
    <PublicLayout>
      <CompetitionsDashboard concursos={concursos} />
    </PublicLayout>
  );
}
