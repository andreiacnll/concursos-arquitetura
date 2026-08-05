type Props = {
  nivel?: string;
};


export default function RiskGauge({
  nivel = "Médio",
}: Props) {


  const valor =
    nivel === "Baixo"
      ? 25
      : nivel === "Alto"
      ? 80
      : 55;



  const rotation = -90 + (valor * 1.8);



  return (

    <div className="risk-gauge-wrapper">


      <svg
        width="140"
        height="80"
        viewBox="0 0 140 80"
      >

        <path
          d="M20 70 A50 50 0 0 1 120 70"
          fill="none"
          stroke="#e8e8e2"
          strokeWidth="10"
          strokeLinecap="round"
        />


        <path
          d="M20 70 A50 50 0 0 1 120 70"
          fill="none"
          stroke="#6d9360"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray="157"
          strokeDashoffset={
            157 - (157 * valor / 100)
          }
        />



        <line
          x1="70"
          y1="70"
          x2="70"
          y2="35"
          stroke="#222"
          strokeWidth="3"
          transform={`rotate(${rotation} 70 70)`}
        />

      </svg>


      <strong>
        {nivel}
      </strong>


    </div>

  );

}
