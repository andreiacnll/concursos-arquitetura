import "@/components/analise/dashboard/dashboard.css";
import PrivateLayout from "@/components/layout/PrivateLayout";
import HeroAnalise from "@/components/analise/dashboard/HeroAnalise";
import MetricsBar from "@/components/analise/dashboard/MetricsBar";
import DecisionDashboard from "@/components/analise/dashboard/DecisionDashboard";
import Timeline from "@/components/analise/dashboard/Timeline";
import UpdatesBox from "@/components/analise/dashboard/UpdatesBox";
import ProjectInfoPanel from "@/components/analise/dashboard/ProjectInfoPanel";
import ConcursoConcecaoAnalysis from "@/components/analise/ConcursoConcecaoAnalysis";
import DocumentInsightsCards from "@/components/analise/DocumentInsightsCards";
import CompanyMatchingSection from "@/components/analise/CompanyMatchingSection";
import AnalysisPresentationV2, { type AnalysisPresentation } from "@/components/analise/AnalysisPresentationV2";
import SemanticAnalysisFacts from "@/components/analise/SemanticAnalysisFacts";
import DesignCompetitionAnalysis from "@/components/analise/DesignCompetitionAnalysis";
import { API_URL } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";

type Props = {
  params: {
    id: string;
  };
};

/**
 * Adapta dados de concurso de conceção para o formato dos componentes CNLL.
 * Converte ficha.analise_ai.vale_a_pena_concorrer → decisao
 */
function adaptarDecisaoConcecao(ficha: any) {
  const analiseAi = ficha?.analise_ai || {};
  const valePena = analiseAi?.vale_a_pena_concorrer || {};
  return {
    score: { valor: analiseAi?.score || 0 },
    classificacao: valePena?.veredito || "—",
    oportunidades: analiseAi?.oportunidades || [],
    risco: {
      nivel: analiseAi?.complexidade === "Alta" ? "Alto"
           : analiseAi?.complexidade === "Média" ? "Médio"
           : "Baixo"
    },
    elegibilidade: {
      estado: (valePena?.probabilidade_exclusao || "").includes("Baixa") ? "Compatível" : "Avaliar",
      motivos: analiseAi?.riscos || []
    },
  };
}

/**
 * Adapta programa de conceção para o formato dos concursos normais.
 */
function adaptarProgramaConcecao(ficha: any) {
  const programa = ficha?.programa || {};
  const normalizarAreas = (valor: any) => {
    if (Array.isArray(valor)) {
      return Object.fromEntries(valor.map((a: string) => [String(a), ""]));
    }
    if (valor && typeof valor === "object") {
      return valor;
    }
    if (typeof valor === "string" && valor.trim()) {
      return { [valor.trim()]: "" };
    }
    return {};
  };
  return {
    descricao: programa?.resumo_intervencao,
    resumo: programa?.resumo_intervencao || "Informação não disponível nos documentos analisados",
    tipo: programa?.tipo_intervencao ? [programa.tipo_intervencao] : [],
    funcoes: programa?.funcoes_identificadas || [],
    usos: programa?.funcoes_identificadas || [],
    areas: normalizarAreas(programa?.areas),
    observacoes_ai: programa?.condicionantes?.length
      ? `Condicionantes: ${programa.condicionantes.join("; ")}`
      : null,
  };
}

export default async function AnalisePage({
  params,
}: Props) {

  const { id } = await params;
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const authHeaders = session?.access_token
    ? { Authorization: `Bearer ${session.access_token}` }
    : undefined;

  const resposta = await fetch(
    `${API_URL}/analise/${id}`,
    {
      cache: "no-store",
      headers: authHeaders,
    }
  );

  if (!resposta.ok) {
    return (
      <main className="site-container">
        <h1>Análise não encontrada</h1>
      </main>
    );
  }

  const dados = await resposta.json();
  const ficha = dados.analise;

  const concursoResposta = await fetch(
    `${API_URL}/concursos/${id}`,
    {
      cache: "no-store",
      headers: authHeaders,
    }
  );

  const concurso = concursoResposta.ok
    ? await concursoResposta.json()
    : null;

  let presentation: AnalysisPresentation | null = null;
  if (dados.analise_id) {
    try {
      const presentationResponse = await fetch(`${API_URL}/analises/${dados.analise_id}/presentation`, {
        cache: "no-store",
        headers: authHeaders,
      });
      if (presentationResponse.ok) presentation = await presentationResponse.json();
    } catch {
      presentation = null;
    }
  }

  // Detectar tipo de procedimento
  const tipoProcedimento = (
    concurso?.tipo_procedimento ||
    ficha?.identificacao?.tipo_procedimento ||
    ""
  ).toLowerCase();

  const isConcursoConcecao = tipoProcedimento.includes("concurso de conceção") ||
                              tipoProcedimento.includes("concurso de concecao");

  // ── Dados adaptados para concursos de conceção ──
  const decisaoData = isConcursoConcecao
    ? adaptarDecisaoConcecao(ficha)
    : ficha.decisao;

  const programaData = isConcursoConcecao
    ? adaptarProgramaConcecao(ficha)
    : ficha.programa;

  if (isConcursoConcecao) {
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

  return (
    <PrivateLayout>
      <main className="site-container">
        <HeroAnalise
          identificacao={ficha.identificacao || ficha}
          concurso={concurso}
          concursoId={id}
        />

        <MetricsBar
          investimento={ficha.investimento}
          programa={ficha.programa}
          economia={ficha.economia}
          isConcursoConcecao={isConcursoConcecao}
        />

        {/* ═══ VALE A PENA CONCORRER? (mesmo componente para ambos) ═══ */}
        <div className="ai-decision-section">
          <DecisionDashboard decisao={decisaoData} />
        </div>

        {ficha?.architecture_intelligence?.consolidated ? (
          <SemanticAnalysisFacts
            consolidated={ficha.architecture_intelligence.consolidated}
          />
        ) : presentation ? (
          <AnalysisPresentationV2 data={presentation} />
        ) : (
          <DocumentInsightsCards insights={ficha.document_insights} />
        )}

        <CompanyMatchingSection
          matching={{
            ...ficha.company_matching,
            competition_type: presentation?.competition_type,
            competition_subtype: presentation?.competition_subtype,
          }}
        />

        {!presentation && programaData && (
          <section className="programa-preliminar-section">
            <h2>📐 Programa preliminar analisado</h2>
            <div className="programa-preliminar-content">
              <div className="programa-item">
                <h3>Resumo da intervenção</h3>
                <p>{programaData.resumo}</p>
              </div>

              {programaData.tipo && programaData.tipo.length > 0 && (
                <div className="programa-item">
                  <h3>Tipo de intervenção</h3>
                  <div className="programa-tags">
                    {programaData.tipo.map((t: string, idx: number) => (
                      <span key={idx}>{t}</span>
                    ))}
                  </div>
                </div>
              )}

              {(programaData.usos || programaData.funcoes) && (
                <div className="programa-item">
                  <h3>Principais funções identificadas</h3>
                  <ul>
                    {(programaData.usos || programaData.funcoes || []).map((fn: string, idx: number) => (
                      <li key={idx}>{fn}</li>
                    ))}
                  </ul>
                </div>
              )}

              {programaData.areas && Object.keys(programaData.areas).length > 0 && (
                <div className="programa-item">
                  <h3>Áreas / programa</h3>
                  <div className="programa-tags">
                    {Object.entries(programaData.areas).map(([chave, valor]: [string, any]) => (
                      <span key={chave}>{chave}: {valor}</span>
                    ))}
                  </div>
                </div>
              )}

              {programaData.observacoes_ai && (
                <div className="programa-item">
                  <h3>Observações arquitetónicas</h3>
                  <p>{programaData.observacoes_ai}</p>
                </div>
              )}
            </div>
          </section>
        )}

        {!presentation && isConcursoConcecao && (
          <ConcursoConcecaoAnalysis ficha={ficha} concurso={concurso} />
        )}

        {/* ═══ LAYOUT DUAS COLUNAS (comum a ambos) ═══ */}
        <div className="analysis-layout-reference">

          <div className="analysis-left">

            {!presentation && <Timeline concursoId={id} />}

            <UpdatesBox concursoId={Number(concurso?.id || id)} />

          </div>

          <aside className="analysis-right">
            <ProjectInfoPanel ficha={ficha} />
          </aside>

        </div>

      </main>
    </PrivateLayout>
  );
}
