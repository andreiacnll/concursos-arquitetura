"""Executa os adaptadores complementares de concursos de arquitetura.

Fontes:
- Plataforma Encomenda OA-SRS: importa novos concursos recentes e complementa existentes.
- Espaço de Arquitetura: descoberta editorial com filtro forte e datas oficiais.
- Ordem dos Arquitectos: modo complementar, sem criar cartões novos.

A BASE.gov continua exclusiva de ``app.coletor``.
"""

from __future__ import annotations

# Usa o repositório de certificados do sistema operativo.
# No Windows, isto permite ao Requests validar com a mesma cadeia
# de confiança usada pelo navegador, sem desativar a segurança TLS.
try:
    import truststore
except ImportError:
    truststore = None
else:
    truststore.inject_into_ssl()

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from app.fontes import espaco_arquitetura, oasrs_encomenda, ordem_arquitectos
from app.fontes.common import (
    CHECKPOINT_PATH,
    ExternalProcedure,
    SourceReport,
    load_checkpoint,
    process_source_items,
    procedure_to_dict,
    save_checkpoint,
)


Collector = Callable[[], list[ExternalProcedure]]

ADAPTERS: dict[str, tuple[str, Collector]] = {
    "oasrs": ("Plataforma Encomenda OA-SRS", oasrs_encomenda.collect),
    "ordem": ("Ordem dos Arquitectos", ordem_arquitectos.collect),
    "espaco": ("Espaço de Arquitetura", espaco_arquitetura.collect),
}


def collect_all(
    *,
    selected_sources: list[str],
    dry_run: bool,
    checkpoint_path: Path = CHECKPOINT_PATH,
) -> tuple[dict[str, list[ExternalProcedure]], dict[str, SourceReport]]:
    checkpoint = load_checkpoint(checkpoint_path)
    selected: dict[str, list[ExternalProcedure]] = {}
    reports: dict[str, SourceReport] = {}

    for source_key in selected_sources:
        label, collector = ADAPTERS[source_key]
        try:
            discovered = collector()
            chosen, report = process_source_items(
                discovered,
                dry_run=dry_run,
                checkpoint=checkpoint,
            )
        except Exception as exc:
            chosen = []
            report = SourceReport(
                source=source_key,
                errors=[f"{type(exc).__name__}: {exc}"],
            )
        selected[source_key] = chosen
        reports[source_key] = report
        print_source_report(label, report, chosen, dry_run=dry_run)

    if not dry_run:
        save_checkpoint(checkpoint, checkpoint_path)
    return selected, reports


def print_source_report(
    label: str,
    report: SourceReport,
    procedures: list[ExternalProcedure],
    *,
    dry_run: bool,
) -> None:
    print()
    print(f"{label.upper()} — {'SIMULAÇÃO' if dry_run else 'GRAVAÇÃO'}")
    print(f"- descobertos: {report.discovered}")
    print(f"- ativos/candidatos complementares: {report.active}")
    print(f"- relevantes selecionados: {report.relevant}")
    print(f"- rejeitados: {report.rejected}")
    print(f"- fora da janela: {report.outside_window}")
    print(f"- complementares sem correspondência: {report.complement_only_unmatched}")
    if not dry_run:
        print(f"- novos guardados: {report.inserted}")
        print(f"- associados a concursos existentes: {report.associated}")
        print(f"- já conhecidos: {report.already_known}")
        print(f"- estados atualizados: {report.source_state_updated}")
    if report.errors:
        for error in report.errors:
            print(f"- AVISO: {error}")
    if procedures:
        print("- selecionados:")
        for item in procedures:
            date_part = item.publication_date or "sem data oficial"
            print(f"  · {item.title} | {date_part} | {item.page_url}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recolhe fontes externas complementares de arquitetura."
    )
    parser.add_argument(
        "--source",
        choices=("all", *ADAPTERS.keys()),
        default="all",
        help="Executa apenas uma fonte ou todas.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Consulta e filtra sem alterar a base nem o checkpoint.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Mostra também o resultado normalizado em JSON.",
    )
    args = parser.parse_args()

    sources = list(ADAPTERS) if args.source == "all" else [args.source]
    selected, reports = collect_all(
        selected_sources=sources,
        dry_run=args.dry_run,
    )

    print()
    print("FONTES EXTERNAS — RESUMO")
    print("- coletor BASE.gov alterado: não")
    print("- base de dados adicional: não")
    print("- endpoint novo: não")
    print("- prioridade BASE.gov: preservada")
    print("- Ordem dos Arquitectos: modo complementar")

    if args.json:
        print(
            json.dumps(
                {
                    "sources": {
                        key: [procedure_to_dict(item) for item in value]
                        for key, value in selected.items()
                    },
                    "reports": {
                        key: asdict(value)
                        for key, value in reports.items()
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
