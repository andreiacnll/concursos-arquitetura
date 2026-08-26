import "@/components/analise/dashboard/dashboard.css";
import PrivateLayout from "@/components/layout/PrivateLayout";
import DesignCompetitionAnalysis from "@/components/analise/DesignCompetitionAnalysis";
import { API_URL } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Props = {
  params: {
    id: string;
  };
};

export default async function AnalisePage({ params }: Props) {
  const { id } = await params;

  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const authHeaders = session?.access_token
    ? { Authorization: `Bearer ${session.access_token}` }
    : undefined;

  const freshness = Date.now();

  const resposta = await fetch(
    `${API_URL}/analise/${id}?fresh=${freshness}`,
    {
      cache: "no-store",
      headers: authHeaders,
    },
  );

  if (!resposta.ok) {
    return (
      <PrivateLayout>
        <main className="site-container">
          <h1>Análise não encontrada</h1>
        </main>
      </PrivateLayout>
    );
  }

  const dados = await resposta.json();
  const ficha = dados.analise;

  const concursoResposta = await fetch(
    `${API_URL}/concursos/${id}?fresh=${freshness}`,
    {
      cache: "no-store",
      headers: authHeaders,
    },
  );

  const concurso = concursoResposta.ok
    ? await concursoResposta.json()
    : null;

  let presentation: any = null;

  if (dados.analise_id) {
    try {
      const presentationResponse = await fetch(
        `${API_URL}/analises/${dados.analise_id}/presentation?fresh=${freshness}`,
        {
          cache: "no-store",
          headers: authHeaders,
        },
      );

      if (presentationResponse.ok) {
        presentation = await presentationResponse.json();
      }
    } catch {
      presentation = null;
    }
  }

  return (
    <PrivateLayout>
      <DesignCompetitionAnalysis
        ficha={ficha}
        concurso={concurso}
        presentation={presentation}
        concursoId={id}
      />
    </PrivateLayout>
  );
}
