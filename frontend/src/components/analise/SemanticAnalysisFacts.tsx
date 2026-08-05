"use client";

type SemanticItem = {
  field_name?: string;
  value?: unknown;
  normalized_value?: unknown;
  phase?: string;
  knowledge_block?: string;
  confidence?: number;
  source_document?: string;
};

type Props = {
  consolidated?: {
    prices?: Record<string, unknown>;
    information_model?: SemanticItem[];
  } | null;
};

const LABELS: Record<string, string> = {
  competition_prize: "Prémios do concurso",
  procedure_value: "Valor do procedimento",
  design_services_value: "Valor dos serviços de projeto",
  estimated_construction_cost: "Custo estimado da obra",
  submission_panel_quantity: "Quantidade de painéis",
  submission_panel_format: "Formato dos painéis",
  descriptive_memory: "Memória descritiva",
  digital_files: "Ficheiros digitais",
  model_requirement: "Maquete",
  video_requirement: "Vídeo",
  anonymity_requirement: "Anonimato",
  submission_platform: "Plataforma de entrega",
  submission_deadline: "Prazo de entrega",
  execution_project: "Projeto de execução",
  technical_assistance: "Assistência técnica",
  final_drawings: "Telas finais",
  measurements: "Medições",
  approval_requirement: "Aprovações necessárias",
};

const FINANCIAL_TYPES = [
  "competition_prize",
  "procedure_value",
  "design_services_value",
  "estimated_construction_cost",
];

function text(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value.replace(/\s+/g, " ").trim();
  if (typeof value === "number") return String(value);
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    return text(obj.value ?? obj.normalized_value ?? obj.amount ?? "");
  }
  return "";
}

function isUsable(value: string): boolean {
  const normalized = value.toLowerCase();
  return Boolean(
    value &&
      value !== "0" &&
      value !== "0.0" &&
      value !== "0,0" &&
      value.length <= 240 &&
      !normalized.includes("não identificado") &&
      !normalized.includes("nao identificado")
  );
}

function itemValue(item?: SemanticItem): string {
  if (!item) return "";
  return text(item.value) || text(item.normalized_value);
}

function formatLabel(type: string): string {
  return LABELS[type] || type.replace(/_/g, " ");
}

function ValueCard({
  label,
  value,
  source,
}: {
  label: string;
  value: string;
  source?: string;
}) {
  const confirmed = isUsable(value);
  return (
    <article className="semantic-fact-card">
      <span className="semantic-fact-label">{label}</span>
      <strong>{confirmed ? value : "Por confirmar"}</strong>
      <span className={confirmed ? "semantic-status confirmed" : "semantic-status pending"}>
        {confirmed ? "Confirmado" : "Por confirmar"}
      </span>
      {confirmed && source ? <small>{source}</small> : null}
    </article>
  );
}

export default function SemanticAnalysisFacts({ consolidated }: Props) {
  const items = Array.isArray(consolidated?.information_model)
    ? consolidated!.information_model!
    : [];

  const byType = new Map<string, SemanticItem>();
  for (const item of items) {
    const type = String(item?.field_name || "");
    if (!type || byType.has(type)) continue;
    byType.set(type, item);
  }

  const financial = FINANCIAL_TYPES.map((type) => {
    const item = byType.get(type);
    return {
      type,
      value: itemValue(item),
      source: item?.source_document,
    };
  });

  const submission = items.filter(
    (item) =>
      item?.phase === "submission" ||
      item?.knowledge_block === "submission_deliverables",
  );
  const contract = items.filter(
    (item) =>
      item?.phase === "contract_execution" ||
      item?.knowledge_block === "contract_deliverables",
  );

  if (!items.length && !financial.some((item) => isUsable(item.value))) {
    return null;
  }

  return (
    <section className="semantic-analysis-facts" aria-label="Informação confirmada">
      <div className="semantic-section-heading">
        <span>Informação confirmada</span>
        <h2>Leitura estruturada das peças</h2>
        <p>
          Apenas valores e requisitos associados a evidências documentais são
          apresentados aqui.
        </p>
      </div>

      <section className="semantic-group">
        <div className="semantic-group-title">
          <span>Valores</span>
          <h3>Condições financeiras</h3>
        </div>
        <div className="semantic-facts-grid financial">
          {financial.map((item) => (
            <ValueCard
              key={item.type}
              label={formatLabel(item.type)}
              value={item.value}
              source={item.source}
            />
          ))}
        </div>
      </section>

      <section className="semantic-group">
        <div className="semantic-group-title">
          <span>Candidatura</span>
          <h3>Como participar</h3>
        </div>
        <div className="semantic-facts-grid">
          {submission.length ? (
            submission.map((item, index) => (
              <ValueCard
                key={`${item.field_name}-${index}`}
                label={formatLabel(String(item.field_name || ""))}
                value={itemValue(item)}
                source={item.source_document}
              />
            ))
          ) : (
            <ValueCard label="Elementos de candidatura" value="" />
          )}
        </div>
      </section>

      <section className="semantic-group">
        <div className="semantic-group-title">
          <span>Contrato</span>
          <h3>Obrigações após adjudicação</h3>
        </div>
        <div className="semantic-facts-grid">
          {contract.length ? (
            contract.map((item, index) => (
              <ValueCard
                key={`${item.field_name}-${index}`}
                label={formatLabel(String(item.field_name || ""))}
                value={itemValue(item)}
                source={item.source_document}
              />
            ))
          ) : (
            <ValueCard label="Entregáveis contratuais" value="" />
          )}
        </div>
      </section>

      <style jsx global>{`
        .semantic-analysis-facts {
          display: grid;
          gap: 34px;
          margin: 36px 0;
        }

        .semantic-section-heading span,
        .semantic-group-title span {
          color: #607b43;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.14em;
          text-transform: uppercase;
        }

        .semantic-section-heading h2,
        .semantic-group-title h3 {
          margin: 6px 0 0;
        }

        .semantic-section-heading p {
          max-width: 720px;
          margin: 8px 0 0;
          color: #6f7378;
        }

        .semantic-group {
          display: grid;
          gap: 14px;
        }

        .semantic-facts-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 12px;
        }

        .semantic-facts-grid.financial {
          grid-template-columns: repeat(4, minmax(0, 1fr));
        }

        .semantic-fact-card {
          min-height: 154px;
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 10px;
          padding: 20px;
          border: 1px solid #e5e5e1;
          border-radius: 16px;
          background: #fff;
          overflow: hidden;
        }

        .semantic-fact-label {
          color: #6f7378;
          font-size: 12px;
        }

        .semantic-fact-card strong {
          font-size: clamp(18px, 2vw, 24px);
          line-height: 1.15;
          overflow-wrap: anywhere;
        }

        .semantic-status {
          display: inline-flex;
          padding: 5px 8px;
          border-radius: 999px;
          font-size: 11px;
        }

        .semantic-status.confirmed {
          background: #e8eee1;
          color: #3f542b;
        }

        .semantic-status.pending {
          background: #fff3d8;
          color: #8a5b00;
        }

        .semantic-fact-card small {
          margin-top: auto;
          color: #858982;
          overflow-wrap: anywhere;
        }

        @media (max-width: 1100px) {
          .semantic-facts-grid,
          .semantic-facts-grid.financial {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }

        @media (max-width: 680px) {
          .semantic-facts-grid,
          .semantic-facts-grid.financial {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </section>
  );
}
