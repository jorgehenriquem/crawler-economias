from me_crawler.analytics import analyze, brl, compare


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
