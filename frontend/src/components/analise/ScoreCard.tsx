type Props = {
  score: number;
  classificacao: string;
  oportunidades: string[];
  riscos: string[];
};


export default function ScoreCard({
  score,
  classificacao,
  oportunidades,
  riscos,
}: Props) {


  return (

    <section className="decision-card">


      <div className="score-circle">

        <strong>
          {score}
        </strong>

        <span>
          /100
        </span>

      </div>



      <div className="decision-info">

        <h2>
          Vale a pena concorrer?
        </h2>


        <h3>
          {classificacao}
        </h3>


        <div className="decision-columns">


          <div>

            <h4>
              Pontos positivos
            </h4>

            <ul>

              {oportunidades.map(
                item => (
                  <li key={item}>
                    ✓ {item}
                  </li>
                )
              )}

            </ul>

          </div>



          <div>

            <h4>
              Atenções
            </h4>

            <ul>

              {riscos.map(
                item => (
                  <li key={item}>
                    ⚠ {item}
                  </li>
                )
              )}

            </ul>

          </div>


        </div>


      </div>


    </section>

  );

}
