import RiskCard from "./RiskCard";

type Props = {
  decisao: any;
};

export default function DecisionDashboard({
  decisao,
}: Props) {

  const pontosFortes =
    decisao?.pontos_fortes ??
    decisao?.oportunidades ??
    [];

  const alertas =
    decisao?.alertas ??
    [];

  const score =
    decisao?.score?.valor ??
    decisao?.score ??
    0;


  return (
    <section className="decision-dashboard">

      <div className="decision-title">

        <h2>
          Vale a pena concorrer?
        </h2>

        <p className="decision-subtitle">
          Análise automática para apoiar a decisão do atelier.
        </p>

      </div>


      <div className="decision-content">


        <div className="decision-score">

          <span>
            Score global
          </span>

          <div className="score-circle">

            <strong>
              {score}
            </strong>

            <small>
              /100
            </small>

          </div>

          <h3>
            {decisao?.classificacao}
          </h3>

        </div>



        <div className="decision-points">

          <h4>
            Porque interessa
          </h4>

          <ul>
            {pontosFortes.map(
              (item: string) => (
                <li key={item}>
                  ✓ {item}
                </li>
              )
            )}
          </ul>


          <h4>
            Atenção
          </h4>

          <ul>
            {alertas.map(
              (item: string) => (
                <li key={item}>
                  ⚠ {item}
                </li>
              )
            )}
          </ul>

        </div>



        <div className="eligibility-card">

          <h4>
            Elegibilidade
          </h4>

          <strong>
            {decisao?.elegibilidade?.estado ?? "Não avaliado"}
          </strong>

          <p>
            {decisao?.elegibilidade?.motivos?.join(". ")}
          </p>

        </div>


        <RiskCard />

      </div>


    </section>
  );
}
