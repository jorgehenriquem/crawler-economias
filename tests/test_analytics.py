from me_crawler.analytics import analyze, brl, compare, top_suppliers, detect_duplicates


def _tx(value, type_="GASTO", date="2026-06-10", category="Mercado", **kw):
    return {
        "uuid": f"u-{value}-{date}",
        "value": value,
        "type": type_,
        "date": date,
        "category": {"categoryName": category},
        "isDisabled": False,
        **kw,
    }


def test_brl_formatting():
    assert brl(1234.56) == "R$ 1.234,56"
    assert brl(-99.9) == "R$ 99,90"
    assert brl(0) == "R$ 0,00"


def test_analyze_totals():
    txs = [
        _tx(100.0),
        _tx(50.0, date="2026-06-11"),
        _tx(300.0, type_="GANHO"),
        _tx(999.0, isDisabled=True),  # ignorada
    ]
    a = analyze(txs)

    assert a["total_gastos"] == 150.0
    assert a["total_ganhos"] == 300.0
    assert a["resultado"] == 150.0
    assert a["n_gastos"] == 2
    assert a["ticket_medio"] == 75.0


def test_analyze_projection_uses_day_span():
    # 100/dia ao longo de 10 dias → projeção de 3000 em 30 dias
    txs = [_tx(100.0, date=f"2026-06-{d:02d}") for d in range(1, 11)]
    a = analyze(txs)
    assert round(a["projected"]) == 3000


def test_ma7_window():
    txs = [_tx(100.0, date=f"2026-06-{d:02d}") for d in range(1, 11)]
    a = analyze(txs)
    assert len(a["ma7"]) == len(a["days"])
    assert a["ma7"][0] == 100.0  # janela de 1
    assert a["ma7"][-1] == 100.0  # série constante


def test_compare_deltas():
    current = analyze([_tx(200.0), _tx(100.0, category="Lazer")])
    previous = analyze([_tx(100.0), _tx(50.0, category="Transporte")])

    c = compare(current, previous)

    assert c is not None
    assert c["delta_pct"] == 100.0  # 150 → 300
    mercado = next(r for r in c["rows"] if r["category"] == "Mercado")
    assert mercado["delta_pct"] == 100.0
    lazer = next(r for r in c["rows"] if r["category"] == "Lazer")
    assert lazer["delta_pct"] is None  # categoria nova


def test_compare_returns_none_without_previous_data():
    current = analyze([_tx(100.0)])
    assert compare(current, analyze([])) is None


# ── recent ────────────────────────────────────────────────────────────────────

def test_recent_sorted_descending():
    txs = [
        _tx(10.0, date="2026-06-01"),
        _tx(20.0, date="2026-06-03"),
        _tx(30.0, date="2026-06-02"),
    ]
    a = analyze(txs)
    dates = [t["date"] for t in a["recent"]]
    assert dates == sorted(dates, reverse=True)


def test_recent_includes_all_types():
    txs = [
        _tx(50.0, type_="GASTO",  date="2026-06-01"),
        _tx(200.0, type_="GANHO", date="2026-06-02"),
    ]
    a = analyze(txs)
    types = {t["type"] for t in a["recent"]}
    assert "GASTO" in types
    assert "GANHO" in types


def test_recent_excludes_disabled():
    txs = [
        _tx(100.0, date="2026-06-01"),
        _tx(999.0, date="2026-06-02", isDisabled=True),
    ]
    a = analyze(txs)
    assert all(not t.get("isDisabled") for t in a["recent"])
    assert len(a["recent"]) == 1


# ── filtro de categoria (agregação JS replicada em Python) ────────────────────

def test_by_cat_sums_correctly():
    txs = [
        _tx(100.0, category="Alimentação"),
        _tx(60.0,  category="Alimentação"),
        _tx(200.0, category="Transporte"),
    ]
    a = analyze(txs)
    assert a["by_cat"]["Alimentação"] == 160.0
    assert a["by_cat"]["Transporte"] == 200.0


def test_by_cat_sorted_descending():
    txs = [
        _tx(50.0,  category="Lazer"),
        _tx(200.0, category="Mercado"),
        _tx(100.0, category="Saúde"),
    ]
    a = analyze(txs)
    values = list(a["by_cat"].values())
    assert values == sorted(values, reverse=True)


def test_top_suppliers_groups_by_description():
    txs = [
        _tx(80.0,  **{"description": "SUPERMERCADO"}),
        _tx(120.0, **{"description": "SUPERMERCADO"}),
        _tx(50.0,  **{"description": "FARMACIA"}),
    ]
    result = top_suppliers(txs)
    names = [s["name"] for s in result]
    assert "SUPERMERCADO" in names
    super_entry = next(s for s in result if s["name"] == "SUPERMERCADO")
    assert super_entry["total"] == 200.0
    assert super_entry["count"] == 2


def test_detect_duplicates_finds_same_value_and_category():
    txs = [
        _tx(99.90, date="2026-06-01", **{"description": "NETFLIX"}),
        _tx(99.90, date="2026-06-02", **{"description": "NETFLIX 2"}),
        _tx(10.00, date="2026-06-01", **{"description": "CAFE"}),
    ]
    dups = detect_duplicates(txs)
    assert len(dups) == 1
    assert dups[0]["value"] == 99.90
    assert dups[0]["days_apart"] == 1


def test_detect_duplicates_ignores_outside_window():
    txs = [
        _tx(99.90, date="2026-06-01"),
        _tx(99.90, date="2026-06-10"),  # 9 dias — fora da janela de 3
    ]
    dups = detect_duplicates(txs)
    assert len(dups) == 0
