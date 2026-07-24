type Props = {
  score: number;
  classificacao: string;
};


export default function ScoreCard({
  score,
  classificacao,
}: Props) {

  return (

    <div className="score-card">

      <div className="score-circle">

        <strong>
          {score}
        </strong>

        <span>
          /100
        </span>

      </div>


      <h3>
        {classificacao}
      </h3>


      <p>
        Avaliação automática baseada no valor,
        critérios, documentação disponível e
        exigências técnicas do concurso.
      </p>

    </div>

  );
}
