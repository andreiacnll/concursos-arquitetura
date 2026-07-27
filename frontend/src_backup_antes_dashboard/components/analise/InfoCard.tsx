export default function InfoCard({
  titulo,
  valor,
  icon,
}: {
  titulo: string;
  valor: string;
  icon?: string;
}) {
  return (
    <div className="info-card">
      <span>
        {icon}
        {titulo}
      </span>

      <strong>
        {valor}
      </strong>
    </div>
  );
}
