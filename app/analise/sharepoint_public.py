from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import requests


DEFAULT_TIMEOUT = int(os.getenv("CNLL_SHAREPOINT_TIMEOUT", "45"))
DEFAULT_MAX_DEPTH = int(os.getenv("CNLL_SHAREPOINT_MAX_DEPTH", "8"))
DEFAULT_MAX_FILES = int(os.getenv("CNLL_SHAREPOINT_MAX_FILES", "250"))
DEFAULT_INTERVAL = float(os.getenv("CNLL_SHAREPOINT_LIST_INTERVAL", "1.5"))

USER_AGENT = os.getenv(
    "CNLL_SHAREPOINT_USER_AGENT",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
)

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".zip",
    ".7z",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
    ".txt",
    ".dwg",
    ".dxf",
    ".ifc",
    ".rvt",
}

_G_LIST_DATA_MARKER = "var g_listData = "


@dataclass(slots=True)
class SharePointPublicFile:
    external_id: str
    source_url: str
    context_url: str
    server_relative_url: str
    filename: str
    relative_path: str
    modified_at: str = ""
    created_at: str = ""


class SharePointDiscoveryError(RuntimeError):
    pass


def is_sharepoint_public_url(value: object) -> bool:
    text = str(value or "").strip().casefold()
    return bool(text) and (
        "sharepoint.com" in text
        or "1drv.ms" in text
        or "onedrive.live.com" in text
    )


def _with_download_parameter(url: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["download"] = "1"
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _extract_json_object(text: str, start: int) -> str:
    while start < len(text) and text[start].isspace():
        start += 1
    if start >= len(text) or text[start] != "{":
        raise SharePointDiscoveryError(
            "O bloco g_listData não começa por um objeto JSON."
        )

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    raise SharePointDiscoveryError(
        "O objeto JSON g_listData ficou incompleto."
    )


def parse_list_data(html: str) -> dict[str, Any]:
    marker_index = html.find(_G_LIST_DATA_MARKER)
    if marker_index < 0:
        raise SharePointDiscoveryError(
            "A página pública do SharePoint não contém g_listData."
        )

    json_start = marker_index + len(_G_LIST_DATA_MARKER)
    payload_text = _extract_json_object(html, json_start)

    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as error:
        raise SharePointDiscoveryError(
            f"O g_listData não contém JSON válido: {error}"
        ) from error

    if not isinstance(payload, dict):
        raise SharePointDiscoveryError(
            "O g_listData não é um objeto."
        )
    return payload


def list_rows_from_html(html: str) -> list[dict[str, Any]]:
    payload = parse_list_data(html)
    list_data = payload.get("ListData") or {}
    rows = list_data.get("Row") or []
    return [
        item
        for item in rows
        if isinstance(item, dict)
    ]


def _server_relative_from_response(
    response_url: str,
    rows: list[dict[str, Any]],
) -> str:
    parts = urlsplit(response_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    folder = str(query.get("id") or "").strip()
    if folder:
        return folder

    path = parts.path
    if "/_layouts/" not in path and path:
        return path

    refs = [
        str(item.get("FileRef") or "").strip()
        for item in rows
        if str(item.get("FileRef") or "").strip()
    ]
    if refs:
        common = posixpath.commonpath(refs)
        if any(str(item.get("FSObjType")) == "0" for item in rows):
            return posixpath.dirname(common) if "." in posixpath.basename(common) else common
        return common

    return ""


def _public_listing_url(origin: str, server_relative_url: str) -> str:
    encoded = quote(server_relative_url, safe="/")
    return _with_download_parameter(
        f"{origin}{encoded}?ga=1"
    )


def _public_file_url(origin: str, server_relative_url: str) -> str:
    encoded = quote(server_relative_url, safe="/")
    return _with_download_parameter(
        f"{origin}{encoded}"
    )


def _relative_path(root: str, current: str) -> str:
    root_clean = root.rstrip("/")
    current_clean = current.rstrip("/")
    if current_clean == root_clean:
        return posixpath.basename(current_clean)
    if current_clean.startswith(root_clean + "/"):
        return current_clean[len(root_clean) + 1 :]
    return posixpath.basename(current_clean)


def _timestamp_from_row(row: dict[str, Any], key: str) -> str:
    value = str(row.get(key) or "").strip()
    if ";#" in value:
        value = value.split(";#", 1)[1]
    return value


def _session() -> requests.Session:
    try:
        import truststore
    except Exception:
        pass
    else:
        try:
            truststore.inject_into_ssl()
        except Exception:
            pass

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/json;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.5",
        }
    )
    return session


def _fetch_listing(
    session: requests.Session,
    url: str,
    *,
    timeout: int,
) -> tuple[str, str]:
    response = session.get(
        _with_download_parameter(url),
        timeout=timeout,
        allow_redirects=True,
    )
    response.raise_for_status()

    content_type = response.headers.get(
        "content-type",
        "",
    ).casefold()
    if "html" not in content_type:
        raise SharePointDiscoveryError(
            "A pasta pública do SharePoint não devolveu HTML."
        )
    return response.text, response.url


def discover_public_sharepoint_files(
    sharing_url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_files: int = DEFAULT_MAX_FILES,
    interval: float = DEFAULT_INTERVAL,
) -> list[SharePointPublicFile]:
    if not is_sharepoint_public_url(sharing_url):
        raise SharePointDiscoveryError(
            "O endereço não parece uma partilha pública SharePoint/OneDrive."
        )

    session = _session()
    try:
        first_html, first_final_url = _fetch_listing(
            session,
            sharing_url,
            timeout=timeout,
        )
        first_rows = list_rows_from_html(first_html)
        origin = _origin(first_final_url)
        root_ref = _server_relative_from_response(
            first_final_url,
            first_rows,
        )

        if not root_ref:
            raise SharePointDiscoveryError(
                "Não foi possível determinar a pasta raiz pública."
            )

        queue: list[
            tuple[str, str, list[dict[str, Any]] | None, int]
        ] = [
            (sharing_url, root_ref, first_rows, 0),
        ]
        visited_folders: set[str] = set()
        visited_files: set[str] = set()
        files: list[SharePointPublicFile] = []

        while queue:
            listing_url, folder_ref, prefetched_rows, depth = queue.pop(0)
            if folder_ref in visited_folders:
                continue
            visited_folders.add(folder_ref)

            if depth > max_depth:
                continue

            if prefetched_rows is None:
                if interval > 0:
                    time.sleep(interval)
                html, _ = _fetch_listing(
                    session,
                    listing_url,
                    timeout=timeout,
                )
                rows = list_rows_from_html(html)
            else:
                rows = prefetched_rows

            for row in rows:
                file_ref = str(
                    row.get("FileRef") or ""
                ).strip()
                file_name = str(
                    row.get("FileLeafRef") or ""
                ).strip()
                if not file_ref or not file_name:
                    continue

                is_folder = str(
                    row.get("FSObjType") or ""
                ).strip() == "1"

                if is_folder:
                    if depth < max_depth:
                        queue.append(
                            (
                                _public_listing_url(
                                    origin,
                                    file_ref,
                                ),
                                file_ref,
                                None,
                                depth + 1,
                            )
                        )
                    continue

                if file_ref in visited_files:
                    continue
                visited_files.add(file_ref)

                suffix = Path(file_name).suffix.casefold()
                if suffix and suffix not in SUPPORTED_EXTENSIONS:
                    continue

                relative = _relative_path(
                    root_ref,
                    file_ref,
                )
                files.append(
                    SharePointPublicFile(
                        external_id=str(
                            row.get("UniqueId")
                            or row.get("ID")
                            or file_ref
                        ).strip("{}"),
                        source_url=_public_file_url(
                            origin,
                            file_ref,
                        ),
                        context_url=sharing_url,
                        server_relative_url=file_ref,
                        filename=file_name,
                        relative_path=relative,
                        modified_at=_timestamp_from_row(
                            row,
                            "Modified.",
                        )
                        or _timestamp_from_row(
                            row,
                            "Modified",
                        ),
                        created_at=_timestamp_from_row(
                            row,
                            "Created_x0020_Date",
                        ),
                    )
                )

                if len(files) >= max_files:
                    return files

        return files
    finally:
        session.close()


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Inventário sem download integral de uma pasta pública "
            "SharePoint/OneDrive."
        )
    )
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument(
        "--db",
        default="",
        help="SQLite do projeto para ler referências Lisboa SRU.",
    )
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
    )
    parser.add_argument(
        "--require-files",
        action="store_true",
    )
    args = parser.parse_args()

    targets: list[tuple[str, str]] = [
        (f"url-{index}", url)
        for index, url in enumerate(
            args.url,
            start=1,
        )
    ]

    if args.db:
        connection = sqlite3.connect(args.db)
        connection.row_factory = sqlite3.Row
        try:
            references = args.reference or [
                "SRU20260000204CP",
                "SRU20260000299CP",
                "SRU20260000323CPI",
            ]
            placeholders = ",".join(
                "?"
                for _ in references
            )
            rows = connection.execute(
                f"""
                SELECT referencia, documentos_url
                FROM concurso_fontes
                WHERE fonte = 'lisboa_sru'
                  AND referencia IN ({placeholders})
                ORDER BY referencia
                """,
                references,
            ).fetchall()
            targets.extend(
                (
                    str(row["referencia"]),
                    str(row["documentos_url"]),
                )
                for row in rows
                if row["documentos_url"]
            )
        finally:
            connection.close()

    output: dict[str, Any] = {}
    failed = False

    for label, url in targets:
        try:
            documents = discover_public_sharepoint_files(
                url,
            )
        except Exception as error:
            output[label] = {
                "url": url,
                "error": (
                    f"{type(error).__name__}: {error}"
                ),
                "documents": [],
            }
            failed = failed or args.require_files
            continue

        output[label] = {
            "url": url,
            "count": len(documents),
            "documents": [
                asdict(document)
                for document in documents
            ],
        }
        if args.require_files and not documents:
            failed = True

    print(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_cli())
