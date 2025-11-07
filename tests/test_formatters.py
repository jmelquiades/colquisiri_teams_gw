from src.teams_gw.formatters import format_n2sql_payload

def test_table_columns_rows():
    payload = {"columns": ["a", "b"], "rows": [[1, 2], [3, 4]], "sql": "select 1"}
    md = format_n2sql_payload(payload)
    assert "a | b" in md and "1 | 2" in md and "SQL:" in md

def test_table_data_records():
    payload = {"data": [{"x": 10, "y": 20}, {"x": 30, "y": 40}]}
    md = format_n2sql_payload(payload)
    assert "x | y" in md and "10 | 20" in md

def test_fallback_json():
    payload = {"unexpected": 1}
    md = format_n2sql_payload(payload)
    assert md.startswith("````json")
