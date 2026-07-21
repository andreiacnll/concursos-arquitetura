import Link from "next/link";
import ConcursosList from "@/components/ConcursosList";

type Concurso = {
  id: number;
  titulo: string;
  entidade: string;
  link: string;
  data: string;
  relevante: number;
  data_limite: string | null;
  preco_base: string | null;
  estado: "aberto" | "encerrado" | "sem_prazo";
};

async function getHistorico(): Promise<Concurso[]> {
  const res = await fetch(
    "http://127.0.0.1:8000/historico?estado=todos&limite=100",
    {
      cache: "no-store",
    },
  );

  if (!res.ok) {
    throw new Error("Erro ao carregar o histórico");
  }

  const data = await res.json();
  return data.resultados;
}

export default async function HistoricoPage() {
  const concursos = await getHistorico();

  return (
    <main className="min-h-screen bg-slate-100">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-blue-600">
                Concursos públicos de arquitetura
              </p>

              <h1 className="mt-2 text-4xl font-bold tracking-tight text-slate-900">
                ArquiConcursos
              </h1>

              <p className="mt-3 max-w-2xl text-slate-600">
                Consulta concursos publicados em anos anteriores.
              </p>
            </div>

            <nav className="flex gap-2">
              <Link
                href="/"
                className="rounded-xl bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-200"
              >
                Concursos
              </Link>

              <Link
                href="/historico"
                className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
              >
                Histórico
              </Link>
            </nav>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 py-10">
        <div className="mb-6">
          <h2 className="text-2xl font-semibold text-slate-900">
            Histórico de concursos
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            Concursos publicados antes do ano atual.
          </p>
        </div>

        <ConcursosList concursos={concursos} />
      </section>
    </main>
  );
}
