type Props = {
  nivel?: string;
};


export default function EligibilityCard({
  nivel = "Compatível",
}: Props) {

  return (

    <div className="eligibility-card">

      <h4>
        Nível de elegibilidade
      </h4>


      <strong>
        {nivel}
      </strong>


      <p>
        A maioria dos ateliers consegue participar,
        desde que cumpra os requisitos mínimos.
      </p>


    </div>

  );

}
