import CompetitionsDashboard from "@/components/CompetitionsDashboard";
import Navbar from "@/components/Navbar";
import type { Concurso } from "@/components/competition-types";

async function getConcursos(): Promise<Concurso[]> {
  try {
    const response = await fetch(
      "http://127.0.0.1:8000/concursos?estado=todos&limite=100",
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
    <main>
      <Navbar />
      <CompetitionsDashboard concursos={concursos} />
    </main>
  );
}
