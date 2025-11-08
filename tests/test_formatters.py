from src.teams_gw.formatters import format_n2sql_payload

def test_table_columns_rows():
    payload = {"columns": ["a", "b"], "rows": [[1, 2], [3, 4]], "sql": "select 1"}
    md = format_n2sql_payload(payload)
    assert "a | b" in md and "1 | 2" in md and "SQL:" in md

def test_table_columns_rows_dicts():
    payload = {
        "columns": ["cliente", "fecha"],
        "rows": [
            {"cliente": "A", "fecha": "2024-01-01", "extra": 1},
            {"cliente": "B", "fecha": "2024-01-02", "extra": 2},
        ],
    }
    md = format_n2sql_payload(payload)
    assert "cliente | fecha" in md
    assert "A | 2024-01-01" in md

def test_table_data_records():
    payload = {"data": [{"x": 10, "y": 20}, {"x": 30, "y": 40}]}
    md = format_n2sql_payload(payload)
    assert "x | y" in md and "10 | 20" in md

def test_table_rows_dicts_without_columns():
    payload = {
        "rows": [
            {"cliente": "A", "total": 10},
            {"cliente": "B", "total": 20},
        ]
    }
    md = format_n2sql_payload(payload)
    assert "cliente | total" in md
    assert "B | 20" in md

def test_limit_override():
    payload = {"columns": ["a"], "rows": [[1], [2], [3]]}
    md = format_n2sql_payload(payload, max_rows=2)
    assert "1" in md and "2" in md and "3" not in md

def test_fallback_json():
    payload = {"unexpected": 1}
    md = format_n2sql_payload(payload)
    assert md.startswith("````json")
