from __future__ import annotations

import csv
import json
import re
import zipfile
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


READER_VERSION = "spreadsheet-reader-v1"
SPREADSHEET_EXTENSIONS = {".xlsx", ".xls", ".csv"}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: Any) -> str:
    text = _clean(value).lower()
    for source, target in (
        ("á", "a"), ("à", "a"), ("ã", "a"), ("â", "a"),
        ("é", "e"), ("ê", "e"), ("í", "i"),
        ("ó", "o"), ("ô", "o"), ("õ", "o"),
        ("ú", "u"), ("ç", "c"),
    ):
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", text).strip()


def _parse_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = _clean(value).replace("\xa0", " ")
    if not text:
        return None
    match = re.search(
        r"[-+]?\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?"
        r"|[-+]?\d+(?:[.,]\d+)?",
        text,
    )
    if not match:
        return None
    number = match.group(0).replace(" ", "")
    if "," in number:
        number = number.replace(".", "").replace(",", ".")
    elif number.count(".") > 1:
        number = number.replace(".", "")
    try:
        return float(number)
    except ValueError:
        return None


def _format_area(value: float | None) -> str:
    if value is None:
        return ""
    rendered = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", " ")
    if rendered.endswith(",00"):
        rendered = rendered[:-3]
    return f"{rendered} m²"


def _column_index(reference: str) -> int:
    match = re.match(r"[A-Z]+", reference.upper())
    if not match:
        return 0
    value = 0
    for char in match.group(0):
        value = value * 26 + (ord(char) - 64)
    return max(0, value - 1)


def _xlsx_sheets_stdlib(path: Path) -> list[tuple[str, list[tuple[int, list[Any]]]]]:
    main_ns = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    rel_ns = {
        "p": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", main_ns):
                shared.append(
                    "".join(node.text or "" for node in item.findall(".//m:t", main_ns))
                )

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            item.attrib.get("Id", ""): item.attrib.get("Target", "")
            for item in relationships.findall("p:Relationship", rel_ns)
        }

        output: list[tuple[str, list[tuple[int, list[Any]]]]] = []
        for sheet in workbook.findall("m:sheets/m:sheet", main_ns):
            name = sheet.attrib.get("name", "Folha")
            relationship_id = sheet.attrib.get(f"{{{main_ns['r']}}}id", "")
            target = targets.get(relationship_id, "").lstrip("/")
            if not target:
                continue
            if not target.startswith("xl/"):
                target = "xl/" + target
            if target not in names:
                continue

            sheet_root = ET.fromstring(archive.read(target))
            rows: list[tuple[int, list[Any]]] = []
            for fallback_row, row_node in enumerate(
                sheet_root.findall(".//m:sheetData/m:row", main_ns),
                start=1,
            ):
                try:
                    row_number = int(row_node.attrib.get("r", fallback_row))
                except (TypeError, ValueError):
                    row_number = fallback_row
                values: dict[int, Any] = {}
                for cell in row_node.findall("m:c", main_ns):
                    column = _column_index(cell.attrib.get("r", "A1"))
                    cell_type = cell.attrib.get("t", "")
                    inline = cell.find("m:is", main_ns)
                    value_node = cell.find("m:v", main_ns)
                    raw: Any = ""
                    if inline is not None:
                        raw = "".join(
                            node.text or "" for node in inline.findall(".//m:t", main_ns)
                        )
                    elif value_node is not None:
                        raw = value_node.text or ""
                        if cell_type == "s":
                            try:
                                raw = shared[int(raw)]
                            except (ValueError, IndexError):
                                pass
                        elif cell_type == "b":
                            raw = raw == "1"
                        elif cell_type not in {"str", "inlineStr", "e"}:
                            try:
                                parsed = float(raw)
                                raw = int(parsed) if parsed.is_integer() else parsed
                            except ValueError:
                                pass
                    values[column] = raw
                width = max(values.keys(), default=-1) + 1
                rows.append((row_number, [values.get(index) for index in range(width)]))
            output.append((name, rows))
        return output


def _xls_sheets(path: Path) -> list[tuple[str, list[tuple[int, list[Any]]]]]:
    try:
        import xlrd  # type: ignore
    except Exception:
        return []
    try:
        workbook = xlrd.open_workbook(path)
    except Exception:
        return []
    output: list[tuple[str, list[tuple[int, list[Any]]]]] = []
    for sheet in workbook.sheets():
        rows = [
            (index + 1, list(sheet.row_values(index)))
            for index in range(sheet.nrows)
        ]
        output.append((sheet.name, rows))
    return output


def _csv_sheet(path: Path) -> list[tuple[str, list[tuple[int, list[Any]]]]]:
    encodings = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
    text = ""
    for encoding in encodings:
        try:
            text = path.read_text(encoding=encoding)
            break
        except (OSError, UnicodeError):
            continue
    if not text:
        return []
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    rows = [
        (index, list(row))
        for index, row in enumerate(csv.reader(text.splitlines(), dialect), start=1)
    ]
    return [(path.stem or "CSV", rows)]


def read_sheet_values(path: Path) -> list[tuple[str, list[tuple[int, list[Any]]]]]:
    suffix = path.suffix.casefold()
    if suffix == ".xlsx":
        try:
            return _xlsx_sheets_stdlib(path)
        except Exception:
            return []
    if suffix == ".xls":
        return _xls_sheets(path)
    if suffix == ".csv":
        return _csv_sheet(path)
    return []


def _cell(row: list[Any], index: int | None) -> Any:
    if index is None or index < 0 or index >= len(row):
        return None
    return row[index]


def _header_map(row: list[Any]) -> dict[str, int]:
    normalized = [_norm(value) for value in row]
    columns: dict[str, int] = {}
    area_columns: list[int] = []
    for index, value in enumerate(normalized):
        if not value:
            continue
        if value in {"cod", "cod.", "codigo", "código"} or value.startswith("cod "):
            columns.setdefault("code", index)
        if (
            value in {"espaco", "espaço", "compartimento", "designacao", "designação", "descricao", "descrição", "local"}
            or "compartimento" in value
            or "designacao" in value
        ):
            columns.setdefault("label", index)
        if "grupo" in value or "area funcional" in value or "setor" in value or "sector" in value:
            columns.setdefault("group", index)
        if (
            "quant" in value
            or value in {"qtd", "qt", "n", "nº", "numero", "número", "unidades", "un"}
            or value.startswith("n de ")
        ):
            columns.setdefault("quantity", index)
        if "area" in value or "área" in value or value in {"m2", "m²"}:
            area_columns.append(index)
            if any(token in value for token in ("unit", "por unidade", "unidade")):
                columns.setdefault("unit", index)
            if any(token in value for token in ("total", "global")):
                columns.setdefault("total", index)
            if any(token in value for token in ("prog funcional", "programa funcional", "funcional")):
                columns.setdefault("program_area", index)
            if "proposta" in value:
                columns.setdefault("proposed_area", index)
            if "existente" in value:
                columns.setdefault("existing_area", index)
        if "observ" in value or "nota" in value:
            columns.setdefault("notes", index)

    unused = [index for index in area_columns if index not in columns.values()]
    if "unit" not in columns and unused:
        columns["unit"] = unused[0]
    if "total" not in columns and len(unused) >= 2:
        columns["total"] = unused[-1]
    if "program_area" not in columns and "label" in columns:
        # A common official template has proposed area followed by programme area.
        non_label_areas = [index for index in area_columns if index != columns["label"]]
        if len(non_label_areas) >= 2:
            columns["program_area"] = non_label_areas[-1]
    return columns


def _find_header(rows: list[tuple[int, list[Any]]]) -> tuple[int, int, dict[str, int]] | None:
    best: tuple[int, int, dict[str, int]] | None = None
    best_score = -1
    for position, (row_number, row) in enumerate(rows):
        columns = _header_map(row)
        score = 0
        if "label" in columns:
            score += 10
        if "program_area" in columns:
            score += 12
        if "quantity" in columns:
            score += 4
        if "unit" in columns:
            score += 4
        if "total" in columns:
            score += 4
        normalized = " ".join(_norm(value) for value in row if _clean(value))
        if "compartimento" in normalized:
            score += 8
        if "programa funcional" in normalized or "prog funcional" in normalized:
            score += 8
        if score > best_score and "label" in columns and (
            "program_area" in columns
            or ("quantity" in columns and "unit" in columns and "total" in columns)
        ):
            best_score = score
            best = (position, row_number, columns)
    return best if best_score >= 18 else None


def _valid_label(value: Any) -> bool:
    text = _clean(value)
    normalized = _norm(text)
    if len(text) < 2 or len(text) > 220:
        return False
    if not re.search(r"[A-Za-zÀ-ÿ]", text):
        return False
    if normalized in {"compartimento", "espaco", "designacao", "total", "subtotal"}:
        return False
    if any(token in normalized for token in ("pagina ", "din a1", "din a3")):
        return False
    return True


def _top_level_group(code: str, label: str, area: float | None) -> bool:
    if area is not None:
        return False
    compact_code = re.sub(r"\s+", "", code.upper())
    return bool(re.fullmatch(r"[A-Z]", compact_code)) and bool(label)


def _row_payload(
    *,
    code: str,
    label: str,
    quantity: int,
    unit: float | None,
    total: float,
    group: str,
    source_document: str,
    sheet_name: str,
    source_row: int,
    source_row_end: int,
    notes: str = "",
    method: str,
    confidence: float,
    total_calculated: bool,
) -> dict[str, Any]:
    value = (
        f"{quantity} × {_format_area(unit)} = {_format_area(total)}"
        if quantity > 1 and unit is not None
        else _format_area(total)
    )
    location = (
        f"{sheet_name}!{source_row}:{source_row_end}"
        if source_row_end != source_row
        else f"{sheet_name}!{source_row}"
    )
    return {
        "code": code,
        "label": label,
        "value": value,
        "kind": "functional_area",
        "row_type": "normal",
        "quantity": quantity,
        "quantity_confirmed": True,
        "unit_area_m2": unit,
        "total_area_m2": round(total, 4),
        "total_area_calculated": total_calculated,
        "functional_group": group,
        "source_document": source_document,
        "sheet": sheet_name,
        "source_row": source_row,
        "source_row_end": source_row_end,
        "page": None,
        "notes": notes,
        "evidence_excerpt": f"{label} — {value} ({location})",
        "confidence": confidence,
        "reconstruction_method": method,
    }


def _parse_explicit_schedule(
    rows: list[tuple[int, list[Any]]],
    *,
    header_position: int,
    columns: dict[str, int],
    source_document: str,
    sheet_name: str,
) -> list[dict[str, Any]]:
    if not all(key in columns for key in ("label", "quantity", "unit", "total")):
        return []
    output: list[dict[str, Any]] = []
    current_group = ""
    for row_number, row in rows[header_position + 1 :]:
        label = _clean(_cell(row, columns.get("label")))
        group = _clean(_cell(row, columns.get("group")))
        if group:
            current_group = group
        if not _valid_label(label):
            continue
        quantity_number = _parse_number(_cell(row, columns.get("quantity")))
        unit = _parse_number(_cell(row, columns.get("unit")))
        total = _parse_number(_cell(row, columns.get("total")))
        if quantity_number is None or not float(quantity_number).is_integer():
            continue
        quantity = int(quantity_number)
        if quantity <= 0 or unit is None or unit <= 0:
            continue
        calculated = False
        if total is None:
            total = quantity * unit
            calculated = True
        if total <= 0:
            continue
        expected = quantity * unit
        if abs(expected - total) > max(1.0, expected * 0.05):
            continue
        output.append(
            _row_payload(
                code=_clean(_cell(row, columns.get("code"))),
                label=label,
                quantity=quantity,
                unit=unit,
                total=total,
                group=current_group,
                source_document=source_document,
                sheet_name=sheet_name,
                source_row=row_number,
                source_row_end=row_number,
                notes=_clean(_cell(row, columns.get("notes"))),
                method="spreadsheet_explicit_columns",
                confidence=0.99 if not calculated else 0.96,
                total_calculated=calculated,
            )
        )
    return output


def _parse_repeated_schedule(
    rows: list[tuple[int, list[Any]]],
    *,
    header_position: int,
    columns: dict[str, int],
    source_document: str,
    sheet_name: str,
) -> list[dict[str, Any]]:
    label_column = columns.get("label")
    area_column = columns.get("program_area")
    if label_column is None or area_column is None:
        return []

    output: list[dict[str, Any]] = []
    current_group = ""
    index = header_position + 1
    while index < len(rows):
        row_number, row = rows[index]
        code = _clean(_cell(row, columns.get("code")))
        label = _clean(_cell(row, label_column))
        area = _parse_number(_cell(row, area_column))
        notes = _clean(_cell(row, columns.get("notes")))

        if not label:
            index += 1
            continue
        if _top_level_group(code, label, area):
            current_group = label
            index += 1
            continue

        # Official programme templates often declare a parent line and then
        # enumerate every equal compartment on blank-code rows. Aggregate those
        # physical rows into quantity × unit area, preserving the source span.
        if code and area is None:
            children: list[tuple[int, str, float, str]] = []
            cursor = index + 1
            while cursor < len(rows):
                child_number, child_row = rows[cursor]
                child_code = _clean(_cell(child_row, columns.get("code")))
                child_label = _clean(_cell(child_row, label_column))
                child_area = _parse_number(_cell(child_row, area_column))
                child_notes = _clean(_cell(child_row, columns.get("notes")))
                if child_code:
                    break
                if not child_label and child_area is None:
                    cursor += 1
                    continue
                if child_label and child_area is not None and child_area > 0:
                    children.append((child_number, child_label, child_area, child_notes))
                    cursor += 1
                    continue
                break

            if children and _valid_label(label):
                areas = [item[2] for item in children]
                same_unit = all(abs(value - areas[0]) <= 0.001 for value in areas)
                unit = areas[0] if same_unit else None
                total = sum(areas)
                combined_notes = " · ".join(
                    item for item in [notes, *(child[3] for child in children)] if item
                )
                output.append(
                    _row_payload(
                        code=code,
                        label=label,
                        quantity=len(children),
                        unit=unit,
                        total=total,
                        group=current_group,
                        source_document=source_document,
                        sheet_name=sheet_name,
                        source_row=row_number,
                        source_row_end=children[-1][0],
                        notes=combined_notes,
                        method="spreadsheet_repeated_rows",
                        confidence=0.995 if same_unit else 0.97,
                        total_calculated=True,
                    )
                )
                index = cursor
                continue

        if area is not None and area > 0 and _valid_label(label):
            output.append(
                _row_payload(
                    code=code,
                    label=label,
                    quantity=1,
                    unit=area,
                    total=area,
                    group=current_group,
                    source_document=source_document,
                    sheet_name=sheet_name,
                    source_row=row_number,
                    source_row_end=row_number,
                    notes=notes,
                    method="spreadsheet_program_area_column",
                    confidence=0.99,
                    total_calculated=False,
                )
            )
        index += 1
    return output


def _global_metric_key(label: str) -> str:
    normalized = _norm(label)
    rules = (
        ("area_lote", ("area do lote", "area do terreno")),
        ("area_intervencao", ("area de intervencao", "area total de intervencao")),
        ("area_implantacao_total", ("area de implantacao total",)),
        ("area_bruta_total", ("area bruta de construcao total", "area bruta total")),
        ("area_espacos_exteriores", ("area de espacos exteriores",)),
        ("area_permeavel", ("area permeavel",)),
        ("area_exterior_impermeavel", ("area de espacos exteriores impermeavel",)),
    )
    for key, aliases in rules:
        if any(alias in normalized for alias in aliases):
            return key
    return ""


def _global_metrics(
    rows: list[tuple[int, list[Any]]],
    *,
    stop_position: int,
    source_document: str,
    sheet_name: str,
) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    seen: set[str] = set()
    column_scope: dict[int, str] = {}
    active_scope = "documental"

    # Scope can be conveyed either by dedicated columns or by successive
    # sections using the same value column. Resolve it while walking the
    # rows so a later ``EXISTENTE`` header never overwrites earlier proposal
    # metrics.
    for row_number, row in rows[:stop_position]:
        normalized_cells = [_norm(value) for value in row]
        row_text = " ".join(value for value in normalized_cells if value)
        if "areas globais da proposta" in row_text:
            active_scope = "proposal"
        elif "areas globais do existente" in row_text:
            active_scope = "existing"

        for index, normalized in enumerate(normalized_cells):
            if normalized == "proposta" or "areas globais da proposta" in normalized:
                column_scope[index] = "proposal"
            elif normalized == "existente" or "areas globais do existente" in normalized:
                column_scope[index] = "existing"

        text_cells = [
            _clean(value)
            for value in row
            if _clean(value) and re.search(r"[A-Za-zÀ-ÿ]", _clean(value))
        ]
        if not text_cells:
            continue
        label = max(text_cells, key=len)
        key = _global_metric_key(label)
        if not key or key in seen:
            continue
        numeric_cells = [
            (index, _parse_number(value))
            for index, value in enumerate(row)
            if _parse_number(value) is not None and (_parse_number(value) or 0) > 0
        ]
        if not numeric_cells:
            continue
        index, value = (
            numeric_cells[0]
            if key in {"area_lote", "area_intervencao"}
            else numeric_cells[-1]
        )
        if value is None or value <= 0:
            continue
        seen.add(key)
        scope = (
            "proposal"
            if key in {"area_lote", "area_intervencao"}
            else column_scope.get(index, active_scope)
        )
        metrics.append(
            {
                "key": key,
                "label": label,
                "value": _format_area(value),
                "total_area_m2": value,
                "kind": "global_area",
                "scope": scope,
                "source_document": source_document,
                "sheet": sheet_name,
                "source_row": row_number,
                "evidence_excerpt": f"{label}: {_format_area(value)} ({sheet_name}!{row_number})",
                "confidence": 0.99,
                "reconstruction_method": "spreadsheet_global_metric",
                "documental": True,
            }
        )
    return metrics


def _dedupe_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int | None, float | None, int | None]] = set()
    for row in rows:
        quantity = row.get("quantity") if isinstance(row.get("quantity"), int) else None
        total = _parse_number(row.get("total_area_m2"))
        source_row = row.get("source_row") if isinstance(row.get("source_row"), int) else None
        signature = (
            _norm(row.get("functional_group")),
            _norm(row.get("label")),
            quantity,
            total,
            source_row,
        )
        if signature in seen:
            continue
        seen.add(signature)
        output.append(row)
    return output


def read_spreadsheet_document(path: Path, *, display_name: str | None = None) -> dict[str, Any]:
    path = Path(path)
    source_document = display_name or path.name
    sheets = read_sheet_values(path)
    tables: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not sheets:
        warnings.append("Não foi possível abrir a folha de cálculo.")

    for sheet_name, rows in sheets:
        header = _find_header(rows)
        if header is None:
            continue
        header_position, header_row, columns = header
        explicit = _parse_explicit_schedule(
            rows,
            header_position=header_position,
            columns=columns,
            source_document=source_document,
            sheet_name=sheet_name,
        )
        repeated = _parse_repeated_schedule(
            rows,
            header_position=header_position,
            columns=columns,
            source_document=source_document,
            sheet_name=sheet_name,
        )
        selected = repeated if len(repeated) > len(explicit) else explicit
        selected = _dedupe_rows(selected)
        if not selected:
            continue
        calculated_total = round(
            sum(float(row.get("total_area_m2") or 0) for row in selected),
            4,
        )
        methods = sorted({str(row.get("reconstruction_method") or "") for row in selected})
        groups: list[str] = []
        for row in selected:
            group = _clean(row.get("functional_group"))
            if group and group not in groups:
                groups.append(group)
        tables.append(
            {
                "table_type": "functional_area_schedule",
                "sheet_name": sheet_name,
                "header_row": header_row,
                "columns": columns,
                "rows": selected,
                "row_count": len(selected),
                "reliable_row_count": sum(
                    1 for row in selected if float(row.get("confidence") or 0) >= 0.90
                ),
                "functional_groups": groups,
                "calculated_total_m2": calculated_total,
                "calculated_total_is_documental": False,
                "reconstruction_method": methods[0] if len(methods) == 1 else methods,
                "source_document": source_document,
                "warnings": [
                    "O total resulta da soma das linhas reconstruídas e não substitui um total documental oficial."
                ],
            }
        )
        metrics = _global_metrics(
            rows,
            stop_position=header_position,
            source_document=source_document,
            sheet_name=sheet_name,
        )
        if metrics:
            tables[-1]["global_metrics"] = metrics

    if not tables and sheets:
        warnings.append("Nenhum quadro de áreas reconhecido com confiança suficiente.")

    return {
        "version": READER_VERSION,
        "source_document": source_document,
        "format": path.suffix.casefold().lstrip("."),
        "tables": tables,
        "warnings": warnings,
    }


def spreadsheet_to_text(result: dict[str, Any]) -> str:
    lines = [
        f"SPREADSHEET SOURCE: {result.get('source_document', '')}",
        f"SPREADSHEET READER: {result.get('version', READER_VERSION)}",
    ]
    for table in result.get("tables") or []:
        lines.append(
            "FUNCTIONAL AREA SCHEDULE | "
            f"sheet={table.get('sheet_name', '')} | "
            f"rows={table.get('row_count', 0)} | "
            f"method={table.get('reconstruction_method', '')}"
        )
        for metric in table.get("global_metrics") or []:
            lines.append(
                "GLOBAL AREA | "
                f"key={metric.get('key', '')} | "
                f"label={metric.get('label', '')} | "
                f"value={metric.get('value', '')} | "
                f"sheet={metric.get('sheet', '')} | row={metric.get('source_row', '')}"
            )
        for row in table.get("rows") or []:
            lines.append(
                "FUNCTIONAL AREA | "
                f"group={row.get('functional_group', '')} | "
                f"code={row.get('code', '')} | "
                f"space={row.get('label', '')} | "
                f"quantity={row.get('quantity', '')} | "
                f"unit_area_m2={row.get('unit_area_m2', '')} | "
                f"total_area_m2={row.get('total_area_m2', '')} | "
                f"sheet={row.get('sheet', '')} | "
                f"rows={row.get('source_row', '')}-{row.get('source_row_end', '')}"
            )
        total = table.get("calculated_total_m2")
        if total is not None:
            lines.append(
                "CALCULATED SCHEDULE TOTAL | "
                f"value={_format_area(float(total))} | documental=false"
            )
    for warning in result.get("warnings") or []:
        lines.append(f"SPREADSHEET WARNING: {warning}")
    return "\n".join(lines).strip()


def extract_spreadsheet_text(path: Path, *, display_name: str | None = None) -> tuple[str, dict[str, Any]]:
    result = read_spreadsheet_document(path, display_name=display_name)
    return spreadsheet_to_text(result), result


def structured_tables_from_results(results: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for result in results:
        for table in result.get("tables") or []:
            if isinstance(table, dict):
                tables.append(table)
    return tables


def dumps_result(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)
