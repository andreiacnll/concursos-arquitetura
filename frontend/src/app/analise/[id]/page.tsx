import "@/components/analise/dashboard/dashboard.css";
import MostrarMais from "@/components/MostrarMais";
import PrivateLayout from "@/components/layout/PrivateLayout";
import MetricCard from "@/components/analise/MetricCard";
import ScoreCard from "@/components/analise/ScoreCard";
import HeroAnalise from "@/components/analise/dashboard/HeroAnalise";
import MetricsBar from "@/components/analise/dashboard/MetricsBar";
import DecisionDashboard from "@/components/analise/dashboard/DecisionDashboard";
import Timeline from "@/components/analise/dashboard/Timeline";
import UpdatesBox from "@/components/analise/dashboard/UpdatesBox";
import AnalysisPanels from "@/components/analise/dashboard/AnalysisPanels";
import ProjectInfoPanel from "@/components/analise/dashboard/ProjectInfoPanel";
import ProjectSummary from "@/components/analise/dashboard/ProjectSummary";
import EligibilityCard from "@/components/analise/dashboard/EligibilityCard";
import RiskCard from "@/components/analise/dashboard/RiskCard";
import ConcursoConcecaoAnalysis from "@/components/analise/ConcursoConcecaoAnalysis";




import {
  Euro,
  Ruler,
  CalendarDays
} from "lucide-react";




const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";


type Props = {
  params: {
    id: string;
  };
};


export default async function AnalisePage({
  params,
}: Props) {

  const { id } = await params;


  const resposta = await fetch(
    `${API_URL}/analise/${id}`,
    {
      cache: "no-store",
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
    }
  );


  const concurso = concursoResposta.ok
    ? await concursoResposta.json()
    : null;


  // Detectar tipo de procedimento
  const tipoProcedimento = (
    concurso?.tipo_procedimento ||
    ficha?.identificacao?.tipo_procedimento ||
    ""
  ).toLowerCase();

  const isConcursoConcecao = tipoProcedimento.includes("concurso de conceção") ||
                              tipoProcedimento.includes("concurso de concecao");


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

        {/* Renderização condicional baseada no tipo de procedimento */}
        {isConcursoConcecao ? (
          <ConcursoConcecaoAnalysis
            ficha={ficha}
            concurso={concurso}
          />
        ) : (
          <>
            {/* Decisão AI - Destaque amarelo - apenas para concursos normais */}
            <div className="ai-decision-section">
              <DecisionDashboard
                decisao={ficha.decisao}
              />
            </div>

            {/* Programa preliminar - apenas para concursos normais */}
            {ficha.programa && (
              <section className="programa-preliminar-section">
                <h2>📐 Programa preliminar analisado</h2>
                <div className="programa-preliminar-content">
                  <div className="programa-item">
                    <h3>Resumo da intervenção</h3>
                    <p>
                      {ficha.programa.descricao ||
                        ficha.programa.resumo ||
                        "Informação não disponível nos documentos analisados"}
                    </p>
                  </div>

                  {ficha.programa.tipo && ficha.programa.tipo.length > 0 && (
                    <div className="programa-item">
                      <h3>Tipo de intervenção</h3>
                      <div className="programa-tags">
                        {ficha.programa.tipo.map((tipo: string, idx: number) => (
                          <span key={idx}>{tipo}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {(ficha.programa.usos || ficha.programa.funcoes) && (
                    <div className="programa-item">
                      <h3>Principais funções identificadas</h3>
                      <ul>
                        {(ficha.programa.usos || ficha.programa.funcoes || []).map((funcao: string, idx: number) => (
                          <li key={idx}>{funcao}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {ficha.programa.areas && Object.keys(ficha.programa.areas).length > 0 && (
                    <div className="programa-item">
                      <h3>Áreas/programas relevantes</h3>
                      <div className="programa-tags">
                        {Object.entries(ficha.programa.areas).map(([chave, valor]: [string, any]) => (
                          <span key={chave}>{chave}: {valor}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {ficha.programa.observacoes_ai && (
                    <div className="programa-item">
                      <h3>Observações arquitetónicas</h3>
                      <p>{ficha.programa.observacoes_ai}</p>
                    </div>
                  )}
                </div>
              </section>
            )}
          </>
        )}


        <div className="analysis-layout-reference">


          <div className="analysis-left">

            <Timeline concursoId={id} />


            {!isConcursoConcecao && (
              <AnalysisPanels
                estrategia={ficha.estrategia}
                analise={ficha}
                equipa={ficha.equipa}
                decisao={ficha}
              />
            )}


            <UpdatesBox />


          </div>


          <aside className="analysis-right">

            <ProjectInfoPanel ficha={ficha} />

          </aside>


        </div>


      </main>


    </PrivateLayout>
  );
}