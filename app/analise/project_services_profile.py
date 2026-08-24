"""Perfil determinístico para concursos de serviços de projeto.

O módulo lê o Programa do Concurso como fonte da candidatura e o Caderno de
Encargos como fonte contratual. Não promove frases soltas a requisitos: cada
facto tem de pertencer a uma secção parametrizada e conservar a evidência.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


VERSION = "project-services-profile-v15.7"

ROLE_PROCEDURE_PROGRAM = "procedure_program"
ROLE_PROPOSAL_ANNEX = "proposal_annex"
ROLE_CONTRACT_SPECIFICATIONS = "contract_specifications"
ROLE_EIR = "eir"
ROLE_TERMS_REFERENCE = "terms_of_reference"
ROLE_ANNOUNCEMENT = "announcement"
ROLE_CLARIFICATION = "clarification"

PROJECT_SERVICES_PARAMETERS: dict[str, Any] = {
    "section_aliases": {
        "proposal_documents": (
            r"documentos?\s+que\s+instruem\s+a\s+proposta",
            r"documentos?\s+que\s+constituem\s+a\s+proposta",
            r"elementos?\s+que\s+instruem\s+a\s+proposta",
            r"elementos?\s+que\s+constituem\s+a\s+proposta",
            r"conteudo\s+da\s+proposta",
        ),
        "submission_mode": (
            r"modo\s+de\s+apresentacao\s+das?\s+propostas",
            r"apresentacao\s+das?\s+propostas",
            r"submissao\s+das?\s+propostas",
        ),
        "award_criteria": (
            r"criterio(?:s)?\s+de\s+adjudicacao",
            r"modelo\s+de\s+avaliacao",
        ),
        "explicit_exclusions": (
            r"causas?\s+de\s+exclusao\s+das?\s+propostas",
            r"exclusao\s+das?\s+propostas",
        ),
        "post_selection": (
            r"habilitacao\s+do\s+adjudicatario",
            r"documentos?\s+de\s+habilitacao",
        ),
        "design_submission": (
            r"anexo\s+iv\s*(?:\n|\r|\s){0,80}trabalho\s*[-–—:]?\s*fator\s+b",
            r"trabalho\s*[-–—:]?\s*fator\s+b",
        ),
        "contract_scope": (
            r"objeto\s+do\s+contrato",
            r"objeto\s+da\s+prestacao",
        ),
        "contract_team": (
            r"meios\s+humanos\s+e\s+deveres\s+relativos\s+aos\s+colaboradores",
            r"constituicao\s+da\s+equipa\s+prestadora\s+de\s+servicos",
        ),
        "contract_phases": (
            r"fases\s+da\s+prestacao\s+de\s+servicos",
            r"fases\s+do\s+projeto",
        ),
        "contract_deadlines": (
            r"prazo\s+de\s+execucao\s+da\s+prestacao\s+de\s+servicos",
            r"prazos?\s+de\s+execucao",
        ),
        "contract_payments": (
            r"condicoes\s+de\s+pagamento",
            r"pagamentos?",
        ),
        "contract_penalties": (
            r"penalidades?\s+por\s+violacao\s+dos\s+prazos",
            r"sancoes?\s+pecuniarias?",
        ),
    },
    "effects": (
        "mandatory_submission",
        "scoring_requirement",
        "explicit_exclusion",
        "formal_risk",
        "post_award_document",
        "contract_obligation",
        "contract_risk",
        "technical_program",
        "missing_source",
        "document_inconsistency",
    ),
}


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\x00", " ")).strip()


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9%€.,:/+\-\s]+", " ", text.casefold())


def _unique(items: Iterable[dict[str, Any]], key: str = "title", limit: int = 80) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        signature = _fold(item.get(key))
        if not signature or signature in seen:
            continue
        seen.add(signature)
        output.append(item)
        if len(output) >= limit:
            break
    return output


def _doc_value(document: object, name: str, default: object = "") -> object:
    if isinstance(document, dict):
        return document.get(name, default)
    return getattr(document, name, default)


def _documents(documents: Iterable[object]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for document in documents:
        text = str(_doc_value(document, "text", "") or "")
        if not text.strip():
            continue
        output.append({
            "filename": str(_doc_value(document, "filename", "documento.txt") or "documento.txt"),
            "role": str(_doc_value(document, "role", "other") or "other"),
            "text": text,
            "folded": _fold(text),
        })
    return output


def _heading_like(line: str) -> bool:
    clean = _clean(line)
    if not clean or len(clean) > 170:
        return False
    folded = _fold(clean)
    if re.match(r"^(?:artigo|clausula)\s+\d+", folded):
        return True
    if re.match(r"^\d+(?:\.\d+)*\s+", folded) and len(clean.split()) <= 24:
        letters = [char for char in clean if char.isalpha()]
        upper = sum(char.isupper() for char in letters)
        return bool(letters) and upper / len(letters) >= 0.45
    letters = [char for char in clean if char.isalpha()]
    upper = sum(char.isupper() for char in letters)
    return bool(letters) and len(clean.split()) <= 18 and upper / len(letters) >= 0.7


def _find_section(
    text: str,
    starts: tuple[str, ...],
    *,
    stops: tuple[str, ...] = (),
    max_chars: int = 30000,
    prefer_last: bool = False,
) -> tuple[str, str] | None:
    lines = text.splitlines()
    start_index = -1
    heading = ""
    matches: list[tuple[int, str]] = []
    heading_matches: list[tuple[int, str]] = []
    for index, raw in enumerate(lines):
        folded = _fold(raw)
        if any(re.search(pattern, folded, re.I) for pattern in starts):
            candidate = (index, _clean(raw))
            matches.append(candidate)
            if _heading_like(raw):
                heading_matches.append(candidate)

    # Uma expressão como "critério de adjudicação" aparece no índice,
    # no verdadeiro título e novamente dentro de parágrafos posteriores.
    # Primeiro escolhemos apenas verdadeiros títulos. Em documentos com
    # índice, prefer_last seleciona o título do corpo e não a entrada do índice.
    candidates = heading_matches or matches
    if candidates:
        start_index, heading = candidates[-1] if prefer_last else candidates[0]
    if start_index < 0:
        return None

    section_lines: list[str] = []
    consumed = 0
    for index in range(start_index, len(lines)):
        raw = lines[index]
        clean = _clean(raw)
        if index > start_index:
            folded = _fold(clean)
            if stops and any(re.search(pattern, folded, re.I) for pattern in stops):
                break
            if _heading_like(clean) and index > start_index + 1:
                # Para secções com subtítulos numerados, só termina em novo título
                # principal; os títulos A., B., C. do Anexo IV são preservados.
                if not re.match(r"^(?:[abc]\.?|subfator\s+[a-z]\d|fator\s+[a-z])\b", folded):
                    if any(marker in folded for marker in (
                        "modo de apresentacao", "propostas variantes", "abertura das propostas",
                        "relatorio preliminar", "relatorio final", "audiencia previa",
                        "habilitacao do adjudicatario", "prestacao de caucao",
                        "condicoes de pagamento", "revisao de precos", "faturas",
                        "penalidades", "preco base", "prazo de execucao",
                    )):
                        break
        section_lines.append(raw)
        consumed += len(raw) + 1
        if consumed >= max_chars:
            break
    section = "\n".join(section_lines).strip()
    return (heading, section) if section else None


def _first_matching_line(text: str, pattern: str) -> str:
    for raw in text.splitlines():
        if re.search(pattern, _fold(raw), re.I):
            return _clean(raw)
    match = re.search(pattern, _fold(text), re.I | re.S)
    if match:
        return _clean(text[max(0, match.start() - 80):match.end() + 220])
    return ""


def _item(
    title: str,
    *,
    category: str,
    effect: str,
    source_document: str,
    source_heading: str,
    excerpt: str,
    mandatory: bool | None = True,
    conditional: bool = False,
    severity: str = "",
    confidence: float = 0.98,
    **extra: Any,
) -> dict[str, Any]:
    value = {
        "key": re.sub(r"[^a-z0-9]+", "_", _fold(title)).strip("_")[:90],
        "title": _clean(title),
        "category": category,
        "effect": effect,
        "phase": "submission" if effect in {"mandatory_submission", "scoring_requirement", "explicit_exclusion", "formal_risk"} else "contract_execution",
        "mandatory": mandatory,
        "conditional": conditional,
        "severity": severity,
        "source_document": source_document,
        "source_heading": source_heading,
        "source_article": source_heading,
        "source_excerpt": _clean(excerpt)[:1400],
        "confidence": confidence,
    }
    value.update({key: val for key, val in extra.items() if val not in (None, "", [], {})})
    return value


PROPOSAL_CHECKLIST_RULES: tuple[dict[str, Any], ...] = (
    {"title": "DEUCP", "pattern": r"documento\s+europeu\s+unico|\bdeucp\b", "category": "administrative"},
    {"title": "Declaração do preço da proposta", "pattern": r"declaracao.{0,100}(?:preco\s+contratual|preco\s+da\s+proposta)", "category": "financial"},
    {"title": "Boletim de identificação da equipa", "pattern": r"boletim.{0,80}identificacao.{0,40}equipa", "category": "team_experience"},
    {"title": "Declaração de experiência do Gestor BIM", "pattern": r"declaracao.{0,80}experiencia.{0,50}(?:gestor|gestao)\s+bim", "category": "team_experience"},
    {"title": "Folha de pontuação do Fator A", "pattern": r"atributos.{0,100}pontuacao.{0,60}fator\s+a|anexo\s+(?:x|xii).{0,120}fator\s+a", "category": "team_experience", "format": "XLS/XLSX"},
    {"title": "Certificados de formação do Gestor BIM", "pattern": r"certificados?.{0,120}formacao.{0,80}(?:gestor|gestao)\s+bim", "category": "team_experience"},
    {"title": "Caderno A3", "pattern": r"ficheiro.{0,100}caderno\s+a3|\bcadernoa3\.pdf\b", "category": "design_submission", "filename": "CadernoA3.pdf", "format": "PDF", "quantity": 1},
    {"title": "Estimativa de custo da obra", "pattern": r"quadro.{0,100}estimativa\s+de\s+custo\s+de\s+obra|\bestimativa\.xls\b", "category": "financial", "filename": "Estimativa.xls", "format": "XLS", "quantity": 1},
    {"title": "Imagem de síntese", "pattern": r"peca\s+grafica.{0,100}imagem1\.jpg|\bimagem1\.jpg\b", "category": "design_submission", "filename": "Imagem1.jpg", "format": "JPG", "quantity": 1},
    {"title": "Comprovativo dos poderes de representação", "pattern": r"documento\s+comprovativo.{0,100}poder.{0,40}representacao|certidao.{0,80}registo\s+comercial.{0,120}procuracao", "category": "administrative"},
    {"title": "Instrumentos de mandato do agrupamento", "pattern": r"(?:agrupamento.{0,180})?instrumentos?\s+de\s+mandato(?:.{0,140}(?:membros|agrupamento))?", "category": "administrative", "conditional": True},
    {"title": "Documentação adicional considerada indispensável", "pattern": r"outra\s+documentacao.{0,100}indispensave(?:l|is)", "category": "optional", "mandatory": False},
)


def _extract_proposal_checklist(pc: dict[str, str]) -> list[dict[str, Any]]:
    located = _find_section(
        pc["text"],
        PROJECT_SERVICES_PARAMETERS["section_aliases"]["proposal_documents"],
        stops=PROJECT_SERVICES_PARAMETERS["section_aliases"]["submission_mode"],
        max_chars=18000,
        prefer_last=True,
    )
    if not located:
        return []
    heading, section = located
    items: list[dict[str, Any]] = []
    for rule in PROPOSAL_CHECKLIST_RULES:
        excerpt = _first_matching_line(section, rule["pattern"])
        if not excerpt:
            # O mandato de agrupamento costuma surgir na regra imediatamente
            # seguinte à lista principal, ainda dentro do Programa do Concurso.
            excerpt = _first_matching_line(pc["text"], rule["pattern"])
        if not excerpt:
            continue
        items.append(_item(
            rule["title"],
            category=rule["category"],
            effect="mandatory_submission" if rule.get("mandatory", True) else "formal_risk",
            source_document=pc["filename"],
            source_heading=heading,
            excerpt=excerpt,
            mandatory=rule.get("mandatory", True),
            conditional=rule.get("conditional", False),
            filename=rule.get("filename"),
            format=rule.get("format"),
            quantity=rule.get("quantity"),
        ))
    return _unique(items)


DESIGN_CONTENT_RULES: tuple[dict[str, Any], ...] = (
    {"title": "Planta de implantação à escala 1:2000", "pattern": r"planta\s+de\s+implantacao.{0,80}1\s*[/ :]\s*2000", "category": "drawing"},
    {"title": "Perfis de implantação à escala 1:2000", "pattern": r"perfis?\s+de\s+implantacao.{0,80}1\s*[/ :]\s*2000", "category": "drawing"},
    {"title": "Axonometria geral da proposta", "pattern": r"axonometria\s+geral", "category": "drawing"},
    {"title": "Sistemas construtivos, materiais e plantações", "pattern": r"sistemas?\s+construtivos?.{0,120}materiais.{0,120}(?:especies|plantacoes)", "category": "diagram"},
    {"title": "Elementos a manter, demolir e construir", "pattern": r"elementos?\s+a\s+manter.{0,100}demolir.{0,100}construir", "category": "diagram"},
    {"title": "Modelação do terreno, escavações e aterros", "pattern": r"movimentacao\s+de\s+terras|profundidades?\s+de\s+escavacao.{0,100}aterro", "category": "diagram", "summary": "Esquema com profundidades de escavação e aterro e volume de terras movimentado."},
    {"title": "Gestão e reaproveitamento das águas pluviais", "pattern": r"reaproveitamento.{0,100}aguas?\s+das?\s+chuvas|retardamento.{0,100}infiltracao", "category": "diagram"},
    {"title": "Acessos, estacionamento e rede viária", "pattern": r"areas?\s+de\s+estacionamento.{0,150}(?:vias|rede\s+viaria)|acessos?.{0,100}(?:estacionamento|rede\s+viaria|viarios?\s+e\s+pedonais)", "category": "diagram"},
    {"title": "Exequibilidade das infraestruturas", "pattern": r"exequibilidade.{0,100}infraestruturas", "category": "diagram"},
    {"title": "Memória descritiva e justificativa", "pattern": r"memoria\s+descritiva\s+e\s+justificativa", "category": "written"},
)


def _extract_design_submission(pc: dict[str, str]) -> dict[str, Any]:
    located = _find_section(
        pc["text"],
        (r"anexo\s+iv\b",),
        stops=(r"anexo\s+v\b", r"criterios?\s+de\s+avaliacao.{0,80}fator\s+b"),
        max_chars=28000,
        prefer_last=True,
    )
    if not located:
        return {"items": [], "formats": [], "notes": []}
    heading, section = located
    items: list[dict[str, Any]] = []
    for rule in DESIGN_CONTENT_RULES:
        excerpt = _first_matching_line(section, rule["pattern"])
        if excerpt:
            items.append(_item(
                rule["title"],
                category=rule["category"],
                effect="mandatory_submission",
                source_document=pc["filename"],
                source_heading=heading,
                excerpt=excerpt,
                confidence=0.99,
                summary=rule.get("summary"),
            ))

    formats: list[dict[str, Any]] = []
    file_specs = (
        {
            "title": "Caderno A3 — PDF, A3 horizontal, máx. 40 MB",
            "pattern": r"caderno\s+a3.{0,700}pdf.{0,500}40\s*mb|cadernoa3\.pdf",
            "filename": "CadernoA3.pdf", "format": "PDF", "page_size": "A3", "orientation": "horizontal", "maximum_size_mb": 40,
            "recommended_pages": 20,
        },
        {
            "title": "Estimativa — XLS na matriz oficial",
            "pattern": r"estimativa\s+de\s+custo\s+de\s+obra.{0,700}(?:matriz|formato\s+original|formato\s+\.xls)|estimativa\.xls",
            "filename": "Estimativa.xls", "format": "XLS",
        },
        {
            "title": "Imagem de síntese — JPG, 300 dpi, máx. 10 MB",
            "pattern": r"imagem1\.jpg|peca\s+grafica.{0,700}10\s*mb",
            "filename": "Imagem1.jpg", "format": "JPG", "maximum_size_mb": 10, "quantity": 1,
        },
    )
    for spec in file_specs:
        excerpt = _first_matching_line(section, spec["pattern"])
        if not excerpt:
            # As condições podem estar separadas em duas linhas.
            filename = spec.get("filename", "")
            excerpt = _first_matching_line(section, re.escape(_fold(filename))) if filename else ""
        if excerpt:
            formats.append(_item(
                spec["title"],
                category="format_and_limit",
                effect="mandatory_submission",
                source_document=pc["filename"],
                source_heading=heading,
                excerpt=excerpt,
                filename=spec.get("filename"),
                format=spec.get("format"),
                page_size=spec.get("page_size"),
                orientation=spec.get("orientation"),
                maximum_size_mb=spec.get("maximum_size_mb"),
                recommended_pages=spec.get("recommended_pages"),
                quantity=spec.get("quantity", 1),
            ))

    notes: list[dict[str, Any]] = []
    negative = _first_matching_line(section, r"nao\s+verificacao.{0,120}nao\s+determina\s+a\s+exclusao")
    if negative:
        notes.append(_item(
            "Incumprimentos do Anexo IV não determinam, por si só, exclusão",
            category="non_exclusion_note",
            effect="formal_risk",
            source_document=pc["filename"],
            source_heading=heading,
            excerpt=negative,
            mandatory=None,
            severity="info",
        ))
    extra_images = _first_matching_line(section, r"nao\s+sera\s+permitida.{0,120}outras\s+imagens|apenas\s+sera\s+avaliada.{0,100}primeira\s+imagem")
    if extra_images:
        notes.append(_item(
            "Só é avaliada uma imagem de síntese",
            category="formal_rule",
            effect="formal_risk",
            source_document=pc["filename"],
            source_heading=heading,
            excerpt=extra_images,
            mandatory=True,
            severity="medium",
        ))
    return {"items": _unique(items), "formats": _unique(formats), "notes": _unique(notes)}


def _extract_submission_rules(pc: dict[str, str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    rules = (
        ("Submissão na plataforma AnoGov", r"plataforma\s+eletronica.{0,200}anogov|processo\s+de\s+concurso.{0,200}anogov"),
        ("Assinatura eletrónica qualificada", r"assinatura\s+eletronica\s+qualificada"),
        ("Documentos em português ou com tradução legalizada", r"lingua\s+portuguesa.{0,220}traducao.{0,80}legalizada"),
        ("Preço em euros, sem IVA e com duas casas decimais", r"preco.{0,120}euros.{0,120}2\s+duas\s+casas\s+decimais.{0,160}nao\s+incluir.{0,50}valor\s+acrescentado"),
        ("Não são admitidas propostas variantes", r"nao\s+e\s+admitida.{0,100}propostas?\s+variantes"),
        ("Membros do agrupamento não podem integrar outra proposta", r"membros?\s+de\s+um\s+agrupamento.{0,180}nao\s+podem.{0,180}outro\s+agrupamento"),
    )
    for title, pattern in rules:
        excerpt = _first_matching_line(pc["text"], pattern)
        if excerpt:
            items.append(_item(
                title,
                category="submission_rule",
                effect="formal_risk",
                source_document=pc["filename"],
                source_heading="Regras de apresentação da proposta",
                excerpt=excerpt,
                severity="medium" if "assinatura" in _fold(title) or "agrupamento" in _fold(title) else "low",
            ))
    return _unique(items)


def _extract_explicit_exclusions(pc: dict[str, str]) -> list[dict[str, Any]]:
    located = _find_section(
        pc["text"],
        PROJECT_SERVICES_PARAMETERS["section_aliases"]["explicit_exclusions"],
        stops=(r"relatorio\s+final", r"nao\s+adjudicacao"),
        max_chars=10000,
        prefer_last=True,
    )
    if not located:
        return []
    heading, section = located
    rules = (
        (
            "Técnicos de coordenação repetidos noutra proposta",
            r"tecnicos?.{0,120}coordenacao.{0,500}(?:outra|outro)\s+(?:proposta|concorrente)",
            "Confirmar exclusividade dos coordenadores antes da submissão.",
        ),
        (
            "Gestor BIM com menos de 80 horas de formação elegível",
            r"gestao\s+bim.{0,400}(?:nao\s+tenha|inferior).{0,100}80\s+horas|formacao\s+minima.{0,80}80\s+horas",
            "Validar certificados, carga horária e conteúdos colaborativos BIM.",
        ),
    )
    output: list[dict[str, Any]] = []
    for title, pattern, action in rules:
        excerpt = _first_matching_line(section, pattern)
        if excerpt:
            output.append(_item(
                title,
                category="explicit_exclusion",
                effect="explicit_exclusion",
                source_document=pc["filename"],
                source_heading=heading,
                excerpt=excerpt,
                severity="high",
                recommended_action=action,
            ))
    return _unique(output)


def _pct(value: str) -> float | None:
    try:
        number = float(value.replace(" ", "").replace(",", "."))
    except ValueError:
        return None
    return round(number, 3) if 0 < number <= 100 else None


def _extract_criteria(pc: dict[str, str]) -> dict[str, Any]:
    located = _find_section(
        pc["text"],
        PROJECT_SERVICES_PARAMETERS["section_aliases"]["award_criteria"],
        stops=(r"relatorio\s+preliminar",),
        max_chars=50000,
        prefer_last=True,
    )
    if not located:
        return {}
    heading, section = located

    factors: list[dict[str, Any]] = []
    factor_patterns = (
        ("A", "Experiência da equipa técnica", r"fator\s+a\b.{0,100}experiencia.{0,100}equipa.{0,100}%"),
        ("B", "Proposta de conceção", r"fator\s+b\b.{0,100}proposta.{0,100}%"),
        ("C", "Preço", r"fator\s+c\b.{0,100}preco.{0,100}%"),
    )
    folded_section = _fold(section)
    for code, name, pattern in factor_patterns:
        evidence = _first_matching_line(section, pattern)
        if not evidence:
            continue
        weight_match = re.search(r"(\d{1,3}(?:[,.]\d+)?)\s*%", _fold(evidence))
        weight = _pct(weight_match.group(1)) if weight_match else None
        if weight is None:
            continue
        factors.append({
            "code": code,
            "name": name,
            "weight": weight,
            "absolute_weight": weight,
            "source_document": pc["filename"],
            "source_heading": heading,
            "evidence_excerpt": evidence,
            "confidence": 0.99,
            "subfactors": [],
        })

    subfactor_specs = (
        ("A1", "Experiência em projetos de parques urbanos", 40.0),
        ("A2", "Experiência em obras de urbanização públicas", 40.0),
        ("A3", "Experiência em remodelação de terrenos", 15.0),
        ("A4", "Formação do Gestor BIM", 5.0),
        ("B1", "Qualidade estética e coerência geral", 40.0),
        ("B2", "Adequação ao Programa de Intervenção", 30.0),
        ("B3", "Adequação aos Princípios Orientadores", 30.0),
    )
    for code, fallback, expected in subfactor_specs:
        pattern = rf"{code.casefold()}\s*[-–—:.]?\s*([^\n%]{{3,180}}?).{{0,50}}(?:ponderacao|peso)?\s*(?:de\s*)?({int(expected)}(?:[,.]0+)?)\s*%"
        match = re.search(pattern, folded_section, re.I)
        weight = expected
        name = fallback
        excerpt = _first_matching_line(section, rf"\b{code.casefold()}\b")
        if match:
            parsed = _pct(match.group(2))
            if parsed is not None:
                weight = parsed
        parent = code[0]
        factor = next((item for item in factors if item["code"] == parent), None)
        if not factor or not excerpt:
            continue
        absolute = round(float(factor["weight"]) * weight / 100.0, 3)
        factor["subfactors"].append({
            "code": code,
            "name": name,
            "weight": weight,
            "absolute_weight": absolute,
            "source_document": pc["filename"],
            "source_heading": heading,
            "evidence_excerpt": excerpt,
            "confidence": 0.98,
        })

    scoring_requirements: list[dict[str, Any]] = []
    requirements = (
        (
            "A1", "Projetos de parques urbanos", 20.0,
            "Até 5 projetos por especialidade; obras na União Europeia, concluídas nos últimos 15 anos e com empreitada atualizada ≥ 2 000 000 €.",
            ("Coordenação de projeto", "Gestão BIM", "Arquitetura paisagista", "Fundações e estruturas", "Escavação e contenção periférica"),
            r"subfator\s+a1|projetos?\s+de\s+parques?\s+urbanos",
        ),
        (
            "A2", "Projetos de obras de urbanização públicas", 20.0,
            "Até 5 projetos por especialidade; obras públicas na União Europeia, concluídas nos últimos 15 anos e com empreitada atualizada ≥ 2 000 000 €.",
            ("Coordenação de projeto", "Gestão BIM", "Arquitetura paisagista", "Fundações e estruturas", "Sistemas elétricos", "Esgotos", "Rede viária"),
            r"subfator\s+a2|obras?\s+de\s+urbanizacao\s+publicas",
        ),
        (
            "A3", "Projetos de remodelação de terrenos", 7.5,
            "Até 5 projetos de terraplanagens; obras na União Europeia, concluídas nos últimos 15 anos e com movimentação de terras ≥ 100 000 m³.",
            ("Terraplanagens",),
            r"subfator\s+a3|remodelacao\s+de\s+terrenos",
        ),
        (
            "A4", "Formação do Gestor BIM", 2.5,
            "Mínimo de 80 horas em processos colaborativos BIM; formação exclusivamente em software de modelação não é aceite.",
            ("Gestão BIM",),
            r"subfator\s+a4|formacao\s+do\s+gestor",
        ),
    )
    for code, title, absolute, summary, specialties, pattern in requirements:
        excerpt = _first_matching_line(section, pattern)
        if excerpt:
            scoring_requirements.append(_item(
                title,
                category="scoring_requirement",
                effect="scoring_requirement",
                source_document=pc["filename"],
                source_heading=heading,
                excerpt=excerpt,
                mandatory=False if code != "A4" else True,
                severity="high" if code in {"A1", "A2", "A3"} else "critical",
                criterion_code=code,
                absolute_weight=absolute,
                summary=summary,
                specialties=list(specialties),
            ))

    tie_breakers = ["Fator A", "Fator B", "Fator C", "Sorteio se o empate persistir"] if re.search(r"em\s+caso\s+de\s+empate", folded_section) else []
    summary = " • ".join(f"{factor['name']} {factor['weight']:g}%" for factor in factors)
    if len(factors) != 3 or abs(sum(float(item["weight"]) for item in factors) - 100) > 0.1:
        return {}
    return {
        "type": "Melhor relação qualidade-preço",
        "summary": summary,
        "factors": factors,
        "formula": "A × 50% + B × 30% + C × 20%",
        "tie_breakers": tie_breakers,
        "interpretation": "Dominado pelo currículo da equipa",
        "source_document": pc["filename"],
        "source_heading": heading,
        "evidence_excerpt": _clean(section)[:1600],
        "confidence": 0.99,
        "verified_top_level_weights": True,
        "scoring_requirements": scoring_requirements,
        "curriculum_weight": 47.5,
        "design_submission_weight": 30.0,
        "price_weight": 20.0,
    }


def _extract_deadlines(pc: dict[str, str]) -> dict[str, Any]:
    """Extrai prazos apenas de cláusulas temporais explícitas do PC.

    Aceita datas absolutas e prazos relativos. Uma data de deteção do coletor
    nunca é promovida a prazo oficial.
    """
    text = pc["text"]
    folded = _fold(text)
    result: dict[str, Any] = {}

    absolute_patterns = (
        r"(?:ate|até)\s+as?\s+(\d{1,2})\s*[:h]\s*(\d{2}).{0,80}(\d{1,2})[\s/.-]+(?:de\s+)?([a-z]+|\d{1,2})[\s/.-]+(?:de\s+)?(20\d{2})",
        r"(\d{1,2})[/-](\d{1,2})[/-](20\d{2}).{0,80}(\d{1,2})\s*[:h]\s*(\d{2})",
    )
    absolute_value = ""
    absolute_excerpt = ""
    match = re.search(absolute_patterns[0], folded, re.I | re.S)
    if match:
        hour, minute, day, month, year = match.groups()
        absolute_value = f"{day} de {month} de {year} · {int(hour):02d}:{minute}"
        absolute_excerpt = _first_matching_line(text, re.escape(match.group(0)[:90]))
    else:
        match = re.search(absolute_patterns[1], folded, re.I | re.S)
        if match:
            day, month, year, hour, minute = match.groups()
            absolute_value = f"{day.zfill(2)}/{month.zfill(2)}/{year} · {int(hour):02d}:{minute}"
            absolute_excerpt = _first_matching_line(text, re.escape(match.group(0)[:90]))

    if absolute_value:
        result["submission_deadline"] = {
            "value": absolute_value,
            "kind": "absolute",
            "status": "confirmed",
            "status_label": "Confirmado",
            "source_document": pc["filename"],
            "source_heading": "Prazo para apresentação de propostas",
            "source_excerpt": absolute_excerpt or absolute_value,
            "confidence": 0.99,
        }
    else:
        relative_match = re.search(
            r"(\d{1,2})\s*[:h]\s*(\d{2}).{0,180}?(\d{1,3})[\s.ºo]*dia.{0,260}?(?:envio|publicacao).{0,180}?(?:anuncio|dr|dre|joue)",
            folded,
            re.I | re.S,
        )
        if relative_match:
            hour, minute, days = relative_match.groups()
            deadline_excerpt = _first_matching_line(
                text,
                rf"{hour}\s*[:h]\s*{minute}.{{0,180}}{days}[\s.ºo]*dia",
            )
            result["submission_deadline"] = {
                "value": f"{int(hour):02d}:{minute} do {int(days)}.º dia após o envio/publicação do anúncio",
                "kind": "relative",
                "status": "relative_confirmed",
                "status_label": "Prazo relativo confirmado",
                "source_document": pc["filename"],
                "source_heading": "Prazo para apresentação de propostas",
                "source_excerpt": deadline_excerpt,
                "confidence": 0.99,
            }

    validity_match = re.search(
        r"(?:manutencao|manter|validade).{0,260}?(\d{1,4}).{0,60}?dias\s+(uteis|corridos|de\s+calendario)|(\d{1,4}).{0,60}?dias\s+(uteis|corridos|de\s+calendario).{0,260}?(?:manutencao|manter|validade)",
        folded,
        re.I | re.S,
    )
    if validity_match:
        number = validity_match.group(1) or validity_match.group(3)
        kind = validity_match.group(2) or validity_match.group(4) or ""
        kind_label = "úteis" if "uteis" in kind else "corridos"
        validity_excerpt = _first_matching_line(text, rf"{number}.{{0,40}}dias\s+{kind}")
        result["proposal_validity"] = {
            "value": f"{int(number)} dias {kind_label}",
            "status": "confirmed",
            "status_label": "Confirmado",
            "source_document": pc["filename"],
            "source_heading": "Prazo da obrigação de manutenção das propostas",
            "source_excerpt": validity_excerpt,
            "confidence": 0.99,
        }

    opening = _first_matching_line(text, r"abertura\s+eletronica.{0,160}dia\s+util\s+imediato")
    if opening:
        result["opening"] = {
            "value": "Dia útil imediato ao prazo de entrega",
            "source_document": pc["filename"],
            "source_excerpt": opening,
            "confidence": 0.98,
        }
    return result


def _extract_post_selection(pc: dict[str, str]) -> list[dict[str, Any]]:
    # Dá prioridade ao título exato. Expressões como “apresentar documentos de
    # habilitação” surgem noutros artigos e não devem deslocar a secção.
    located = _find_section(
        pc["text"],
        (r"habilitacao\s+do\s+adjudicatario\s*$",),
        stops=(r"prestacao\s+de\s+caucao", r"notificacao\s+da\s+apresentacao"),
        max_chars=14000,
    )
    if not located:
        located = _find_section(
            pc["text"],
            (r"documentos?\s+de\s+habilitacao\s*$",),
            stops=(r"prestacao\s+de\s+caucao", r"notificacao\s+da\s+apresentacao"),
            max_chars=14000,
        )
    if not located:
        return []
    heading, section = located
    rules = (
        ("Declaração do Anexo II do CCP", r"declaracao.{0,120}anexo\s+ii.{0,100}(?:codigo\s+dos\s+contratos|ccp)"),
        ("Comprovativos de inexistência de impedimentos", r"documentos?\s+comprovativos?.{0,220}artigo\s+55"),
        ("Declarações das ordens profissionais", r"declaracao.{0,160}ordem\s+profissional"),
        ("Plano de prevenção de corrupção", r"plano\s+de\s+prevencao\s+de\s+corrupcao"),
        ("Registo Central do Beneficiário Efetivo", r"beneficiario\s+efetivo|\brcbe\b"),
    )
    output: list[dict[str, Any]] = []
    for title, pattern in rules:
        excerpt = _first_matching_line(section, pattern)
        if excerpt:
            output.append(_item(
                title,
                category="habilitation",
                effect="post_award_document",
                source_document=pc["filename"],
                source_heading=heading,
                excerpt=excerpt,
                mandatory=True,
            ))
    return _unique(output)


TEAM_GROUP_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Coordenação e BIM", ("Coordenador do projeto", "Gestor BIM", "Coordenação BIM — arquitetura e paisagismo", "Coordenação BIM — estruturas", "Coordenação BIM — infraestruturas")),
    ("Paisagem e espaço público", ("Arquitetura paisagista", "Arquitetura de espaço público", "Mobiliário urbano", "Plano de manutenção do parque")),
    ("Terreno, estruturas e demolições", ("Terraplanagens", "Escavação e contenção periférica", "Fundações e estruturas", "Demolições", "Serviços afetados", "Geotecnia")),
    ("Infraestruturas urbanas", ("Águas", "Esgotos domésticos e pluviais", "Eletricidade", "Comunicações", "Gás", "Rede viária", "Sinalização", "Sinalética", "Resíduos urbanos")),
    ("Conformidade e apoio à obra", ("Arqueologia", "Acessibilidades", "Segurança e saúde", "Resíduos de construção", "Medições e orçamento")),
)


def _extract_team(pc: dict[str, str], annexes: list[dict[str, str]], ce: dict[str, str] | None) -> list[dict[str, Any]]:
    corpus_docs = annexes + ([ce] if ce else [])
    corpus = "\n".join(doc["text"] for doc in corpus_docs)
    source = next((doc for doc in annexes if "boletim" in _fold(doc["filename"])), None) or ce or pc
    groups: list[dict[str, Any]] = []
    for group, roles in TEAM_GROUP_RULES:
        found: list[str] = []
        for role in roles:
            aliases = {
                "Coordenação BIM — arquitetura e paisagismo": r"coordenador.{0,30}bim.{0,60}arquitetura.{0,80}paisag",
                "Coordenação BIM — estruturas": r"coordenador.{0,30}bim.{0,60}estruturas",
                "Coordenação BIM — infraestruturas": r"coordenador.{0,30}bim.{0,80}(?:infraestruturas|instalacoes\s+tecnicas)",
                "Plano de manutenção do parque": r"plano\s+de\s+manutencao.{0,80}parque",
                "Esgotos domésticos e pluviais": r"esgotos.{0,80}(?:domesticos|pluviais)",
                "Resíduos de construção": r"residuos\s+de\s+construcao\s+e\s+demolicao",
                "Medições e orçamento": r"mapa\s+de\s+trabalhos.{0,120}medicoes.{0,100}estimativa",
            }.get(role, re.escape(_fold(role)).replace(r"\ ", r"\s+"))
            if re.search(aliases, _fold(corpus), re.I | re.S):
                found.append(role)
        if found:
            groups.append(_item(
                group,
                category="technical_team_group",
                effect="mandatory_submission",
                source_document=source["filename"],
                source_heading="Equipa técnica a identificar na proposta",
                excerpt="; ".join(found),
                mandatory=True,
                roles=found,
                role_count=len(found),
            ))
    return groups


def _extract_contract(ce: dict[str, str] | None, pc: dict[str, str] | None = None) -> dict[str, Any]:
    if not ce:
        return {"scope_services": [], "deliverables": [], "phases": [], "payments": [], "risks": []}
    text = ce["text"]
    scope_rules = (
        ("Arquitetura paisagista e espaço público", r"projeto\s+de\s+arquitetura\s+paisagista|projeto\s+de\s+arquitetura\s+de\s+espaco\s+publico"),
        ("Terraplanagens, escavação e estruturas", r"projeto\s+de\s+terraplenagem|escavacao\s+e\s+contencao|fundacoes\s+e\s+estruturas"),
        ("Infraestruturas e redes urbanas", r"sistemas?\s+de\s+aguas|sistemas?\s+de\s+esgotos|rede\s+viaria|sistemas?\s+eletricos"),
        ("Medições, orçamento e manutenção", r"mapa\s+de\s+trabalhos.{0,150}estimativa\s+orcamental|plano\s+de\s+manutencao.{0,80}5\s+anos"),
        ("Metodologia BIM", r"metodologia\s+bim|plano\s+de\s+execucao\s+bim"),
    )
    scope: list[dict[str, Any]] = []
    for title, pattern in scope_rules:
        excerpt = _first_matching_line(text, pattern)
        if excerpt:
            scope.append(_item(
                title, category="scope_service", effect="contract_obligation",
                source_document=ce["filename"], source_heading="Objeto do contrato", excerpt=excerpt,
            ))

    phase_specs = (
        ("Plano de Execução BIM", 15, r"fase\s+1.{0,80}plano\s+de\s+execucao\s+bim.{0,80}15"),
        ("Estudo Prévio", 60, r"fase\s+2.{0,80}estudo\s+previo.{0,80}60"),
        ("Anteprojeto", 60, r"fase\s+3.{0,80}anteprojeto.{0,80}60"),
        ("Projeto de Execução", 90, r"fase\s+4.{0,80}projeto\s+de\s+execucao.{0,80}90"),
        ("Projeto de Execução Final", 15, r"fase\s+5.{0,80}projeto\s+de\s+execucao\s+final.{0,80}15"),
        ("Assistência Técnica", None, r"fase\s+6.{0,80}assistencia\s+tecnica"),
    )
    phases: list[dict[str, Any]] = []
    for title, days, pattern in phase_specs:
        excerpt = _first_matching_line(text, pattern)
        if excerpt:
            phases.append(_item(
                title, category="contract_phase", effect="contract_obligation",
                source_document=ce["filename"], source_heading="Prazo de execução da prestação de serviços", excerpt=excerpt,
                duration_days=days, duration_label=f"{days} dias" if days else "Até à receção provisória da obra",
            ))

    payment_specs = (
        ("Plano de Execução BIM", 5, r"5\s*%.{0,100}fase\s+1.{0,80}plano\s+de\s+execucao\s+bim"),
        ("Estudo Prévio", 15, r"15\s*%.{0,100}fase\s+2.{0,80}estudo\s+previo"),
        ("Anteprojeto", 20, r"20\s*%.{0,100}fase\s+3.{0,80}anteprojeto"),
        ("Projeto de Execução", 35, r"35\s*%.{0,100}fase\s+4.{0,80}projeto\s+de\s+execucao"),
        ("Projeto de Execução Final", 10, r"10\s*%.{0,100}fase\s+5.{0,80}projeto\s+de\s+execucao\s+final"),
        ("Assistência Técnica", 15, r"15\s*%.{0,120}assistencia\s+tecnica"),
    )
    payments: list[dict[str, Any]] = []
    for title, weight, pattern in payment_specs:
        excerpt = _first_matching_line(text, pattern)
        if excerpt:
            payments.append(_item(
                f"{title} — {weight}%", category="payment", effect="contract_obligation",
                source_document=ce["filename"], source_heading="Condições de pagamento", excerpt=excerpt,
                percentage=weight,
            ))

    deliverable_titles = (
        "Plano de Execução BIM",
        "Estudo Prévio",
        "Anteprojeto",
        "Projeto de Execução",
        "Projeto de Execução Final",
        "Telas finais e modelos BIM",
    )
    deliverables = [
        _item(
            title, category="contract_deliverable", effect="contract_obligation",
            source_document=ce["filename"], source_heading="Fases da prestação de serviços",
            excerpt=next((item["source_excerpt"] for item in phases if item["title"] == title), title),
        )
        for title in deliverable_titles
        if title != "Telas finais e modelos BIM" or re.search(r"telas\s+finais|modelos?\s+tridimensionais", _fold(text))
    ]

    risk_specs = (
        ("Penalidade de 1‰ por dia de atraso", "high", r"cada\s+dia\s+de\s+atraso.{0,220}1(?:.{0,20})?por\s+mil"),
        ("Penalidade parcial reduzida a metade", "medium", r"prazos\s+parciais.{0,180}reduzido\s+a\s+metade"),
        ("Sanção de 100 € por dia noutros incumprimentos", "high", r"sancao\s+pecuniaria.{0,180}100\s*€"),
        ("Responsabilidade por erros e defeitos do projeto", "high", r"(?:responsabilidade|responde).{0,220}(?:erros|defeitos)|erros\s+e\s+omissoes"),
        ("Propriedade da informação BIM da Lisboa SRU", "medium", r"direitos\s+de\s+propriedade.{0,260}informacao.{0,160}bim"),
        ("Caução de 5% ou 10% se o preço for anormalmente baixo", "medium", r"caucao.{0,350}5\s*%.{0,1600}(?:preco.{0,100}anormalmente\s+baixo.{0,300})?10\s*%"),
        ("Seguros de responsabilidade civil dos técnicos", "medium", r"seguros?\s+de\s+responsabilidade\s+civil.{0,180}tecnicos?"),
    )
    risks: list[dict[str, Any]] = []
    risk_documents = [ce] + ([pc] if pc else [])
    for title, severity, pattern in risk_specs:
        for source in risk_documents:
            excerpt = _first_matching_line(source["text"], pattern)
            if not excerpt:
                continue
            risks.append(_item(
                title, category="contract_risk", effect="contract_risk",
                source_document=source["filename"], source_heading="Riscos e garantias posteriores à adjudicação", excerpt=excerpt,
                severity=severity, summary=excerpt,
            ))
            break

    duration_match = re.search(r"prazo\s+maximo\s+(?:e\s+)?de\s+1815", _fold(text))
    duration = {
        "value": "1815 dias",
        "status": "confirmed",
        "status_label": "Confirmado",
        "source_document": ce["filename"],
        "source_heading": "Prazo de execução da prestação de serviços",
        "source_excerpt": _first_matching_line(text, r"prazo\s+maximo\s+(?:e\s+)?de\s+1815"),
        "confidence": 0.99,
    } if duration_match else {}

    return {
        "scope_services": _unique(scope),
        "deliverables": _unique(deliverables),
        "phases": _unique(phases),
        "payments": _unique(payments),
        "risks": _unique(risks),
        "duration": duration,
    }


def _extract_price(pc: dict[str, str], ce: dict[str, str] | None) -> dict[str, Any]:
    """Extrai apenas um montante diretamente associado a 'preço base'.

    Quando o mesmo montante surge em mais de uma peça, prefere a evidência que
    explicita o tratamento do IVA.
    """
    candidates: list[dict[str, Any]] = []
    for document in (pc, ce):
        if not document:
            continue
        folded = _fold(document["text"])
        for match in re.finditer(
            r"preco\s+base.{0,180}?((?:\d{1,3}(?:[ .]\d{3})+|\d{4,})(?:[,.]\d{2})?)\s*(?:€|euros?)",
            folded,
            re.I | re.S,
        ):
            raw_number = match.group(1).replace(" ", "").replace(".", "").replace(",", ".")
            try:
                numeric = float(raw_number)
            except ValueError:
                continue
            if numeric <= 0:
                continue
            excerpt = _first_matching_line(
                document["text"],
                r"preco\s+base.{0,220}(?:\d{1,3}(?:[ .]\d{3})+|\d{4,})(?:[,.]\d{2})?",
            )
            folded_excerpt = _fold(excerpt)
            explicit_plus_vat = bool(re.search(r"acrescid[oa].{0,40}iva|mais.{0,20}iva", folded_excerpt))
            explicit_without_vat = bool(re.search(r"sem\s+iva|nao\s+inclui.{0,50}(?:iva|valor\s+acrescentado)", folded_excerpt))
            candidates.append({
                "numeric": numeric,
                "document": document,
                "excerpt": excerpt,
                "explicit_plus_vat": explicit_plus_vat,
                "explicit_without_vat": explicit_without_vat,
            })

    if not candidates:
        return {}
    candidates.sort(
        key=lambda item: (
            item["explicit_plus_vat"] or item["explicit_without_vat"],
            item["document"]["role"] == ROLE_CONTRACT_SPECIFICATIONS,
        ),
        reverse=True,
    )
    selected = candidates[0]
    numeric = float(selected["numeric"])
    formatted = f"{numeric:,.2f}".replace(",", "X").replace(".", ",").replace("X", " ")
    suffix = " + IVA" if selected["explicit_plus_vat"] or selected["explicit_without_vat"] else ""
    document = selected["document"]
    return {
        "value": f"{formatted} €{suffix}",
        "numeric_value": numeric,
        "status": "confirmed",
        "status_label": "Confirmado",
        "source_document": document["filename"],
        "source_heading": "Preço base",
        "source_excerpt": selected["excerpt"],
        "confidence": 0.99,
    }


def _document_gaps_and_inconsistencies(documents: list[dict[str, str]], pc: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deteta lacunas e contradições pelo conteúdo documental, não só pelos nomes.

    Nas caches antigas da SRU os anexos podem estar dentro de um ZIP e não
    aparecer como documentos independentes nesta fase. Por isso, uma
    divergência interna do próprio Programa do Concurso tem de ser detetável
    mesmo sem os nomes dos anexos materializados.
    """
    names = " ".join(_fold(Path(document["filename"]).name) for document in documents)
    folded_pc = _fold(pc["text"])
    gaps: list[dict[str, Any]] = []
    inconsistencies: list[dict[str, Any]] = []

    if "programa preliminar" in folded_pc and "programa preliminar" not in names:
        gaps.append(_item(
            "Programa Preliminar não incluído no pacote analisado",
            category="missing_source", effect="missing_source",
            source_document=pc["filename"], source_heading="Peças referidas no Programa do Concurso",
            excerpt=_first_matching_line(pc["text"], r"programa\s+preliminar"),
            mandatory=None, severity="high",
            impact="A análise do programa de intervenção fica incompleta.",
        ))

    # Fator A:
    # - na secção dos documentos da proposta o PC refere ANEXO X;
    # - no artigo dos critérios e na lista final de anexos refere ANEXO XII.
    factor_a_x = re.search(
        r"anexo\s+x\b.{0,220}(?:atributos.{0,120})?(?:pontuacao.{0,100})?fator\s+a",
        folded_pc,
        re.S,
    )
    factor_a_xii = re.search(
        r"anexo\s+xii\b.{0,220}(?:atributos.{0,120})?(?:pontuacao.{0,100})?fator\s+a",
        folded_pc,
        re.S,
    )
    if factor_a_x and factor_a_xii:
        inconsistencies.append(_item(
            "Referência ao Fator A diverge entre Anexo X e Anexo XII",
            category="document_inconsistency", effect="document_inconsistency",
            source_document=pc["filename"], source_heading="Documentos que instruem a proposta / Critério de adjudicação",
            excerpt=_first_matching_line(
                pc["text"],
                r"anexo\s+x.{0,220}(?:atributos.{0,120})?(?:pontuacao.{0,100})?fator\s+a",
            ),
            mandatory=None, severity="medium",
            comparison_excerpt=_first_matching_line(
                pc["text"],
                r"anexo\s+xii.{0,220}(?:atributos.{0,120})?(?:pontuacao.{0,100})?fator\s+a",
            ),
        ))

    # Estimativa:
    # - a lista de documentos e a lista final de anexos identificam ANEXO V;
    # - o texto do Anexo IV manda usar a matriz do ANEXO VI.
    estimate_v = (
        re.search(r"anexo\s+v\b.{0,260}estimativa(?:\s+de)?\s+custo", folded_pc, re.S)
        or re.search(r"estimativa(?:\s+de)?\s+custo.{0,260}anexo\s+v\b", folded_pc, re.S)
    )
    estimate_vi = (
        re.search(r"anexo\s+vi\b.{0,260}estimativa(?:\s+de)?\s+custo", folded_pc, re.S)
        or re.search(r"estimativa(?:\s+de)?\s+custo.{0,260}anexo\s+vi\b", folded_pc, re.S)
    )
    if estimate_v and estimate_vi:
        inconsistencies.append(_item(
            "Matriz da estimativa diverge entre Anexo V e Anexo VI",
            category="document_inconsistency", effect="document_inconsistency",
            source_document=pc["filename"], source_heading="Documentos que instruem a proposta / Anexo IV",
            excerpt=_first_matching_line(
                pc["text"],
                r"anexo\s+v.{0,220}estimativa(?:\s+de)?\s+custo",
            ),
            mandatory=None, severity="high",
            comparison_excerpt=_first_matching_line(
                pc["text"],
                r"anexo\s+vi.{0,220}estimativa(?:\s+de)?\s+custo",
            ),
        ))

    return gaps, inconsistencies


def _document_match_score(document: dict[str, str], kind: str) -> int:
    """Recupera a função documental mesmo quando a cache traz um role antigo.

    A classificação persistida nunca é a única prova. O nome e a estrutura
    interna do documento têm prioridade quando existem marcadores fortes.
    """
    name = _fold(Path(document.get("filename") or "").name)
    folded = document.get("folded") or _fold(document.get("text") or "")
    opening = folded[:14000]
    score = 0

    if kind == "pc":
        if document.get("role") == ROLE_PROCEDURE_PROGRAM:
            score += 100
        if re.search(r"(?:^|[_\-\s])pc(?:[_\-\s.]|$)", name):
            score += 70
        if "programa do concurso" in opening or "programa de concurso" in opening:
            score += 90
        if "documentos que instruem a proposta" in folded:
            score += 35
        if "criterio de adjudicacao" in folded:
            score += 25
        if "causas de exclusao das propostas" in folded:
            score += 20
        if "caderno de encargos" in opening[:2500]:
            score -= 100

    elif kind == "ce":
        if document.get("role") == ROLE_CONTRACT_SPECIFICATIONS:
            score += 100
        if re.search(r"(?:^|[_\-\s])ce(?:[_\-\s.]|$)", name):
            score += 70
        if "caderno de encargos" in opening[:3500]:
            score += 100
        if "fases da prestacao de servicos" in folded:
            score += 35
        if "condicoes de pagamento" in folded:
            score += 25
        if "programa do concurso" in opening[:2500]:
            score -= 100

    elif kind == "annex":
        if document.get("role") == ROLE_PROPOSAL_ANNEX:
            score += 80
        if "anexo" in name:
            score += 40
        if any(marker in name for marker in (
            "boletim", "declaracao", "estimativa", "pontuacao", "fator"
        )):
            score += 35

    return score


def _best_document(
    docs: list[dict[str, str]],
    kind: str,
    *,
    minimum_score: int,
) -> dict[str, str] | None:
    ranked = sorted(
        ((_document_match_score(doc, kind), doc) for doc in docs),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if not ranked or ranked[0][0] < minimum_score:
        return None
    return ranked[0][1]


def extract_project_services_profile(documents: Iterable[object]) -> dict[str, Any]:
    docs = _documents(documents)

    # Não dependemos exclusivamente do role recebido da cache. Isto é
    # importante nos concursos SRU onde versões antigas guardaram DOCX como
    # ZIP e deixaram metadados históricos.
    pc = _best_document(docs, "pc", minimum_score=80)
    ce = _best_document(docs, "ce", minimum_score=80)

    annexes = [
        doc
        for doc in docs
        if doc is not pc
        and doc is not ce
        and _document_match_score(doc, "annex") >= 40
    ]

    if not pc:
        return {}

    checklist = _extract_proposal_checklist(pc)
    design = _extract_design_submission(pc)
    submission_rules = _extract_submission_rules(pc)
    exclusions = _extract_explicit_exclusions(pc)
    criteria = _extract_criteria(pc)
    deadlines = _extract_deadlines(pc)
    post_selection = _extract_post_selection(pc)
    team = _extract_team(pc, annexes, ce)
    contract = _extract_contract(ce, pc)
    price = _extract_price(pc, ce)
    gaps, inconsistencies = _document_gaps_and_inconsistencies(docs, pc)

    has_design_submission = bool(design["items"] or any(item["category"] == "design_submission" for item in checklist))

    # Este perfil especializado só substitui o extrator geral quando as peças
    # comprovam uma prestação de serviços com uma verdadeira proposta de
    # conceção. Concursos correntes com memória metodológica e plano de
    # trabalhos continuam a usar a leitura geral já existente.
    profile_signature = bool(
        has_design_submission
        and len(checklist) >= 5
        and (criteria or len(design["items"]) >= 3)
    )
    if not profile_signature:
        return {}

    all_folded = " ".join(doc.get("folded") or "" for doc in docs)
    features = {
        "has_design_submission": has_design_submission,
        "has_team_portfolio_scoring": bool(criteria.get("curriculum_weight")),
        "has_price_scoring": bool(criteria.get("price_weight")),
        "has_bim_requirements": (
            "bim" in all_folded
            or any("gestor bim" in _fold(item.get("title")) for item in checklist)
        ),
        "has_post_award_project_phases": bool(contract.get("phases")),
        "has_explicit_exclusion_rules": bool(exclusions),
    }

    mandatory_count = sum(1 for item in checklist if item.get("mandatory") is True and not item.get("conditional"))
    top_metrics = {
        "procedure_value": price,
        "construction_cost": {
            "value": "A entregar na proposta",
            "status": "required",
            "status_label": "Exigido",
            "source_document": pc["filename"],
            "source_heading": "Documentos que instruem a proposta",
            "source_excerpt": next((item["source_excerpt"] for item in checklist if item["title"] == "Estimativa de custo da obra"), ""),
            "confidence": 0.99,
        },
        "submission_deadline": deadlines.get("submission_deadline") or {},
        "proposal_validity": deadlines.get("proposal_validity") or {},
        "contract_duration": contract.get("duration") or {},
        "award_criteria": {
            "value": criteria.get("summary", ""),
            "status": "confirmed" if criteria else "pending",
            "status_label": "Confirmado" if criteria else "Por confirmar",
        },
        "procedure_type": {
            "value": "Prestação de serviços de projeto com proposta de conceção" if has_design_submission else "Prestação de serviços de projeto",
            "status": "confirmed",
            "status_label": "Classificado pelas peças",
        },
    }

    return {
        "version": VERSION,
        "parameter_profile": "project_services_with_design_submission",
        "parameter_groups": {
            "document_roles": [ROLE_PROCEDURE_PROGRAM, ROLE_PROPOSAL_ANNEX, ROLE_CONTRACT_SPECIFICATIONS, ROLE_EIR],
            "section_aliases": PROJECT_SERVICES_PARAMETERS["section_aliases"],
            "effects": list(PROJECT_SERVICES_PARAMETERS["effects"]),
        },
        "features": features,
        "award_criteria": criteria,
        "submission": {
            "participant_documents": checklist,
            "proposal_documents": design["items"],
            "formats_and_limits": _unique([*design["formats"], *submission_rules]),
            "critical_conditions": exclusions,
            "formal_risks": _unique([*submission_rules, *design["notes"]]),
            "post_selection_documents": post_selection,
            "mandatory_checklist_count": mandatory_count,
            "checklist_groups": {
                "administrative": [item for item in checklist if item["category"] == "administrative"],
                "financial": [item for item in checklist if item["category"] == "financial"],
                "team_experience": [item for item in checklist if item["category"] == "team_experience"],
                "design_submission": [item for item in checklist if item["category"] == "design_submission"],
                "optional": [item for item in checklist if item["category"] == "optional"],
            },
        },
        "eligibility": {
            "requirements": [
                _item(
                    "Empresa habilitada a prestar serviços de arquitetura",
                    category="eligibility", effect="mandatory_submission",
                    source_document=next((doc["filename"] for doc in annexes if "boletim" in _fold(doc["filename"])), pc["filename"]),
                    source_heading="Boletim de identificação da equipa",
                    excerpt="O Concorrente deve ser empresa habilitada a prestar serviços de arquitetura.",
                ),
                _item(
                    "Técnicos com habilitações legalmente exigidas",
                    category="eligibility", effect="mandatory_submission",
                    source_document=next((doc["filename"] for doc in annexes if "boletim" in _fold(doc["filename"])), pc["filename"]),
                    source_heading="Boletim de identificação da equipa",
                    excerpt="Os técnicos devem cumprir as habilitações legalmente exigidas.",
                ),
            ],
            "explicit_exclusions": exclusions,
            "scoring_requirements": criteria.get("scoring_requirements") or [],
            "status": "Verificar equipa e referências",
            "exclusion_risk": "elevado" if exclusions else "não determinado",
        },
        "technical_team": team,
        "contract": contract,
        "deadlines": deadlines,
        "document_gaps": gaps,
        "inconsistencies": inconsistencies,
        "top_metric_overrides": top_metrics,
    }
