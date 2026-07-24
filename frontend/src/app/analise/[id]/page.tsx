import "@/components/analise/dashboard/dashboard.css";
import MostrarMais from "@/components/MostrarMais";
import AnaliseLayout from "@/components/layout/AnaliseLayout";
import MetricCard from "@/components/analise/MetricCard";
import ScoreCard from "@/components/analise/ScoreCard";
import HeroAnalise from "@/components/analise/dashboard/HeroAnalise";
import MetricsBar from "@/components/analise/dashboard/MetricsBar";
import DecisionDashboard from "@/components/analise/dashboard/DecisionDashboard";
import Timeline from "@/components/analise/dashboard/Timeline";
import AnalysisPanels from "@/components/analise/dashboard/AnalysisPanels";
import UpdatesBox from "@/components/analise/dashboard/UpdatesBox";
import ProjectInfoPanel from "@/components/analise/dashboard/ProjectInfoPanel";
import ProjectSummary from "@/components/analise/dashboard/ProjectSummary";
import EligibilityCard from "@/components/analise/dashboard/EligibilityCard";
import RiskCard from "@/components/analise/dashboard/RiskCard";




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


  return (
    <AnaliseLayout>

      <main className="site-container">


        <HeroAnalise
          identificacao={ficha.identificacao || ficha}
        />


        <MetricsBar
          investimento={ficha.investimento}
          programa={ficha.programa}
        />





        
        
        <div className="analysis-layout-reference">


          <div className="analysis-left">


        <DecisionDashboard
          decisao={ficha.decisao}
          criterio_resumo={ficha.criterio_resumo}
        />


            <Timeline concursoId={id} />


            <AnalysisPanels
              estrategia={ficha.estrategia}
              analise={ficha}
              equipa={ficha.equipa}
              decisao={ficha}
              criterio_resumo={ficha.criterio_resumo}
            />


          </div>


          <aside className="analysis-right">

            <ProjectInfoPanel />

          </aside>


        </div>


<UpdatesBox />


      </main>


    </AnaliseLayout>
  );
}
