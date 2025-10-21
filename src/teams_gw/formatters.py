from __future__ import annotations
from typing import Any, Dict, List
from .settings import settings

def format_n2sql_payload(payload: Dict[str, Any]) -> str:
    """Convierte payload a tabla Markdown. Acepta:
    - {"columns": [...], "rows": [[...]]}
    - {"data": [{...}, ...]}
    Si no reconoce el formato, devuelve JSON como bloque.
    """
    headers: List[str] = []
    rows: List[List[Any]] = []

    if isinstance(payload, dict) and "columns" in payload and "rows" in payload:
        headers = [str(c) for c in payload.get("columns", [])]
        rows = payload.get("rows", [])
    elif isinstance(payload, dict) and isinstance(payload.get("data"), list) and payload["data"]:
        first = payload["data"][0]
        if isinstance(first, dict):
            headers = list(first.keys())
            rows = [[item.get(h) for h in headers] for item in payload["data"]]
    else:
        return f"````json\n{payload}\n````"

    total = len(rows)
    rows = rows[: settings.N2SQL_MAX_ROWS]

    if not headers:
        return "_Sin columnas_"

    header_line = " | ".join(headers)
    sep_line = " | ".join(["---"] * len(headers))
    body_lines = [" | ".join("" if v is None else str(v) for v in r) for r in rows]
    table = "\n".join([header_line, sep_line, *body_lines])

    extra = ""
    if total > len(rows):
        extra = f"\n\n_Se muestran {len(rows)}/{total} filas. Configura `N2SQL_MAX_ROWS` para ver más._"

    sql = payload.get("sql") or payload.get("generated_sql") or payload.get("sql_text")
    sql_md = f"\n\n> SQL: `{sql}`" if sql else ""

    return f"{table}{extra}{sql_md}"
