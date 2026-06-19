import csv
import json

from me_crawler.exporter import print_summary, save_csv, save_json


def _tx(value=100.0, type_="GASTO", **kw):
    return {
        "date": "2026-06-10",
        "description": "Mercado",
        "category": {"categoryName": "Alimentação"},
        "subCategory": {"subCategoryName": "Supermercado"},
        "value": value,
        "type": type_,
        "account": {"name": "Nubank"},
        "paymentMethod": "PIX",
        "projected": False,
        "isDisabled": False,
        "isConsolidated": True,
        **kw,
    }


# ── save_json ─────────────────────────────────────────────────────────────────

def test_save_json_creates_valid_file(tmp_path):
    txs = [_tx(), _tx(value=50.0)]
    out = save_json(txs, tmp_path / "out.json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["value"] == 100.0


def test_save_json_returns_path(tmp_path):
    p = tmp_path / "txs.json"
    result = save_json([_tx()], p)
    assert result == p
    assert result.exists()


# ── save_csv ──────────────────────────────────────────────────────────────────

def test_save_csv_has_expected_headers(tmp_path):
    out = save_csv([_tx()], tmp_path / "out.csv")
    reader = csv.DictReader(out.open(encoding="utf-8-sig"))
    assert set(reader.fieldnames) == {
        "data", "descricao", "categoria", "subcategoria",
        "valor", "tipo", "conta", "cartao", "metodo_pagamento",
        "status", "consolidado",
    }


def test_save_csv_row_values(tmp_path):
    out = save_csv([_tx(value=50.0)], tmp_path / "out.csv")
    rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert len(rows) == 1
    r = rows[0]
    assert r["valor"] == "50.0"
    assert r["categoria"] == "Alimentação"
    assert r["metodo_pagamento"] == "PIX"
    assert r["consolidado"] == "Sim"
    assert r["status"] == "CONFIRMADO"
    assert r["conta"] == "Nubank"


def test_save_csv_pending_status(tmp_path):
    out = save_csv([_tx(projected=True)], tmp_path / "out.csv")
    rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert rows[0]["status"] == "PENDENTE"


def test_save_csv_disabled_status(tmp_path):
    out = save_csv([_tx(isDisabled=True)], tmp_path / "out.csv")
    rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert rows[0]["status"] == "DESABILITADO"


def test_save_csv_not_consolidated(tmp_path):
    out = save_csv([_tx(isConsolidated=False)], tmp_path / "out.csv")
    rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert rows[0]["consolidado"] == "Não"


# ── print_summary ─────────────────────────────────────────────────────────────

def test_print_summary_output(capsys):
    txs = [_tx(value=100.0), _tx(value=50.0, type_="GANHO")]
    print_summary(txs, "Junho 2026")
    out = capsys.readouterr().out
    assert "Junho 2026" in out
    assert "R$ 100,00" in out
    assert "R$ 50,00" in out
    assert "Total de transações: 2" in out


def test_print_summary_deficit(capsys):
    txs = [_tx(value=200.0)]
    print_summary(txs, "Teste")
    out = capsys.readouterr().out
    assert "-R$ 200,00" in out
