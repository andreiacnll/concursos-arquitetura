import { Bell, CalendarClock, ExternalLink, FileText, Sparkles } from "lucide-react";

export type Alerta = {
  id: number;
  concurso_id: number;
  tipo: string;
  titulo: string;
  descricao?: string | null;
  dados_extraidos?: Record<string, unknown> | null;
  documento_origem?: string | null;
  documento_anterior?: string | null;
  documento_novo?: string | null;
  link?: string | null;
  data_deteccao: string;
  estado: string;
  relevante?: boolean | number;
  tem_analise?: boolean | number;
  concurso_titulo: string;
  entidade?: string | null;
  concurso_link?: string | null;
};

type Props = {
  alerta: Alerta;
  onGerarAnalise?: (alerta: Alerta) => void;
};

const labels: Record<string, string> = {
  novo_documento: "Novo documento",
  esclarecimento: "Esclarecimento",
  alteracao_prazo: "Alteração de prazo",
  prazo: "Prazo a aproximar-se",
  alteracao_economica: "Alteração económica",
  alteracao_programa: "Alteração programa",
  alteracao_criterio: "Alteração de critérios",
};

function formatarData(valor: string) {
  const data = new Date(valor);
  if (Number.isNaN(data.getTime())) return valor;
  return new Intl.DateTimeFormat("pt-PT", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(data);
}

function textoExtra(alerta: Alerta) {
  const dados = alerta.dados_extraidos || {};
  const partes = [
    dados.antes ? `Antes: ${String(dados.antes)}` : null,
    dados.agora ? `Agora: ${String(dados.agora)}` : null,
    dados.data_limite ? `Data limite: ${String(dados.data_limite)}` : null,
    dados.dias_restantes ? `Dias restantes: ${String(dados.dias_restantes)}` : null,
    dados.documento ? `Documento: ${String(dados.documento)}` : null,
    dados.impacto ? `Impacto: ${String(dados.impacto)}` : null,
  ];

  return partes.filter(Boolean).join(" · ");
}

export default function AlertCard({ alerta, onGerarAnalise }: Props) {
  const tipo = labels[alerta.tipo] || alerta.tipo;
  const linkDocumento = alerta.link || alerta.documento_origem || alerta.concurso_link;
  const relevante = Boolean(alerta.relevante);
  const extra = textoExtra(alerta);

  return (
    <article className="alert-card">
      <div className="alert-symbol">
        {alerta.tipo === "prazo" || alerta.tipo === "alteracao_prazo" ? (
          <CalendarClock size={30} />
        ) : alerta.tipo === "novo_documento" ? (
          <FileText size={30} />
        ) : (
          <Bell size={30} />
        )}
      </div>

      <div className="alert-content">
        <div className="alert-heading">
          <span>{tipo}</span>
          <time>{formatarData(alerta.data_deteccao)}</time>
        </div>

        <h3>{alerta.titulo}</h3>
        <p>{alerta.descricao || "Alteração detetada num concurso acompanhado."}</p>
        <strong>{alerta.concurso_titulo}</strong>
        {alerta.entidade && <small>{alerta.entidade}</small>}

        {extra && <div className="alert-extract">{extra}</div>}

        {relevante && (
          <p className="alert-impact">
            Esta alteração pode influenciar a análise existente.
          </p>
        )}

        <div className="alert-actions">
          {linkDocumento && (
            <a href={linkDocumento} target="_blank" rel="noreferrer">
              <ExternalLink size={15} /> Ver documento
            </a>
          )}

          {alerta.concurso_link && (
            <a href={alerta.concurso_link} target="_blank" rel="noreferrer">
              Ver concurso
            </a>
          )}

          {relevante && onGerarAnalise && (
            <button onClick={() => onGerarAnalise(alerta)}>
              <Sparkles size={15} /> Gerar nova análise AI
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
