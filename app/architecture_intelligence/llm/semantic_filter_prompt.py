from __future__ import annotations

import json
from typing import Any


PROMPT_VERSION = "semantic-filter-v0.3"

SYSTEM_PROMPT = """És uma camada de extração semântica para concursos de arquitetura.

Recebes um conjunto curto de fragmentos retirados literalmente de documentos oficiais.

Regras obrigatórias:
1. Usa exclusivamente os fragmentos fornecidos.
2. Não inventes, completes ou reformules factos, valores, datas, percentagens ou entidades.
3. Extrai todos os factos explícitos e independentes presentes nos fragmentos; não pares após o primeiro.
4. Usa exclusivamente os semantic_types permitidos no pedido.
5. source_excerpt deve copiar literalmente um fragmento curto do conteúdo recebido.
6. Mantém números, unidades e designações como aparecem na evidência.
7. O mesmo montante pode ter significados diferentes. Distingue sempre:
   - prémios do concurso;
   - valor ou preço base do procedimento;
   - valor dos serviços de projeto;
   - custo ou valor estimado da obra;
   - preço contratual;
   - condições de pagamento.
8. Distingue entregas da candidatura de entregáveis e serviços após adjudicação.
9. Para entregáveis contratuais, o value deve identificar o entregável, não a percentagem de pagamento.
10. Ignora índices, cabeçalhos, referências soltas e fragmentos OCR sem significado autónomo.
11. Se nenhum facto estiver claramente comprovado, devolve status insufficient_evidence e facts vazio.
12. Se existir pelo menos um facto comprovado, devolve status ok.
13. Produz apenas JSON compatível com o schema, sem Markdown ou texto adicional."""


def build_semantic_filter_prompt(
    item: dict[str, Any],
    allowed_semantic_types: list[str],
    *,
    max_chars: int = 6000,
) -> dict[str, str]:
    selected = {
        "field_name": item.get("field_name"),
        "declared_knowledge_block": item.get("knowledge_block"),
        "source_document": item.get("source_document"),
        "allowed_semantic_types": allowed_semantic_types,
        "source_fragments": item.get("value"),
    }

    user = json.dumps(
        selected,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    if len(user) > max_chars:
        user = user[:max_chars]

    return {
        "system": SYSTEM_PROMPT,
        "user": user,
    }
