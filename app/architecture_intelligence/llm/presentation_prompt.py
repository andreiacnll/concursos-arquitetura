from __future__ import annotations

import json
from typing import Any

PROMPT_VERSION = "presentation-v3"
ALLOWED_FIELDS = (
    "procedure_identity",
    "prices",
    "award_strategy",
    "required_team",
    "phases_and_deliverables",
    "submission_checklist",
    "drawing_rules",
    "financial_conditions",
    "technical_constraints",
    "exclusion_risks",
    "document_alerts",
    "document_quality",
    "quality_report",
    "evidences",
)

SYSTEM_PROMPT = """És uma camada de apresentação documental. Não decides factos e nunca inventas informação: usa exclusivamente os dados fornecidos pelos readers. Mantém exatamente nomes, datas, prazos, percentagens, valores monetários, prémios e número de vencedores. Distingue prémios, preço dos serviços, valor do procedimento e custo estimado da obra. Classifica o procedimento com base nos dados disponíveis e recomenda a ordem das secções sem apagar factos específicos do concurso. Organiza os cards pela ordem mais adequada ao tipo de procedimento, mas só com secções que tenham conteúdo útil. Deduplica semanticamente preservando todos os evidence_ids. Separa documentos da proposta, habilitação e entregáveis contratuais. Cada card deve ter um título claro, um resumo de uma ou duas frases completas e itens legíveis, sem nomes técnicos de campos, OCR cru ou fragmentos jurídicos. Mantém apenas conteúdo útil e não cries cards vazios. Inclui as evidências estruturadas para consulta no detalhe. Se faltar evidência usa status insufficient_evidence e o resumo: Informação documental insuficiente para confirmar este ponto. Produz apenas JSON que cumpra o schema, sem Markdown, HTML ou texto adicional. Usa exclusivamente message.content como resultado."""


def build_prompt(data: dict[str, Any]) -> dict[str, str]:
    selected = {key: data.get(key) for key in ALLOWED_FIELDS}
    selected["evidence_references"] = _evidence_references(data.get("evidences", []))
    user = json.dumps(selected, ensure_ascii=False, sort_keys=True, default=str)
    return {"system": SYSTEM_PROMPT, "user": user}


def _evidence_references(evidences: Any) -> list[dict[str, Any]]:
    result = []
    for evidence in evidences or []:
        if isinstance(evidence, dict):
            result.append(
                {
                    "evidence_id": evidence.get("evidence_id"),
                    "filename": evidence.get("filename"),
                    "page": evidence.get("page"),
                    "section": evidence.get("section"),
                    "excerpt": evidence.get("excerpt"),
                    "confidence": evidence.get("confidence"),
                }
            )
    return result
