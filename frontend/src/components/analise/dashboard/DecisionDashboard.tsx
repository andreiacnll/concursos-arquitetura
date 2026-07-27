import EligibilityCard from "./EligibilityCard";
import RiskCard from "./RiskCard";

type Props = {
  decisao: any;
  criterio_resumo?: string;
};


export default function DecisionDashboard({
  decisao,
  criterio_resumo,
}: Props) {

  return (
    <section className="decision-dashboard">

      <div className="decision-title">

        <h2>
          Vale a pena concorrer?
        </h2>

        <p className="decision-subtitle">
          A nossa análise rápida para apoiar a sua decisão.
        </p>

      </div>


      <div className="decision-content">


      <div className="decision-score">

        <span>
          Score global
        </span>

        <div className="score-circle">

          <strong>
            {decisao?.score?.valor || decisao?.score || 0}
          </strong>

          <small>
            /100
          </small>

        </div>

        <h3>
          {decisao.classificacao}
        </h3>

      </div>



      <div>

        <h4>
          Principais pontos
        </h4>

        <ul>

          {decisao.oportunidades.map(
            (item:string)=>(
              <li key={item}>
                ✓ {item}
              </li>
            )
          )}

        </ul>


      </div>



      <div className="eligibility-card">

        <h4>
          Nível de elegibilidade
        </h4>

        <strong>
          Compatível
        </strong>

        <p>
          A maioria dos ateliers consegue participar,
          desde que cumpra os requisitos mínimos.
        </p>

      </div>



      <RiskCard />


      </div>


    </section>
  );
}
