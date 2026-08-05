import { ReactNode } from "react";


type Props = {
  titulo: string;
  valor: string;
  icon?: ReactNode;
};


export default function MetricCard({
  titulo,
  valor,
  icon,
}: Props) {

  return (
    <article className="metric-card">

      <div className="metric-icon">
        {icon}
      </div>

      <span>
        {titulo}
      </span>

      <strong>
        {valor}
      </strong>

    </article>
  );

}
