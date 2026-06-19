from me_crawler.analytics import (
    analyze,
    brl,
    compare,
    detect_duplicates,
    dow_weekly_comparison,
    monthly_pattern,
    open_installments,
    top_suppliers,
)


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


# ── dow_weekly_comparison ─────────────────────────────────────────────────────
# 2026-06-01 = Segunda, 2026-06-05 = Sexta

def test_dow_comparison_identifies_most_expensive_day():
    segundas = [_tx(200.0, date=f"2026-06-{d:02d}") for d in (1, 8, 15, 22)]
    sextas   = [_tx( 50.0, date=f"2026-06-{d:02d}") for d in (5, 12, 19, 26)]
    result = dow_weekly_comparison(segundas + sextas)

    assert result is not None
    assert result["most_expensive"] == "Segunda"
    assert result["by_dow"]["Segunda"]["avg"] == 200.0
    assert result["by_dow"]["Sexta"]["avg"] == 50.0


def test_dow_comparison_pct_vs_avg():
    segundas = [_tx(200.0, date=f"2026-06-{d:02d}") for d in (1, 8, 15, 22)]
    sextas   = [_tx(100.0, date=f"2026-06-{d:02d}") for d in (5, 12, 19, 26)]
    result = dow_weekly_comparison(segundas + sextas)

    assert result["by_dow"]["Segunda"]["pct_vs_avg"] > 0
    assert result["by_dow"]["Sexta"]["pct_vs_avg"] < 0


def test_dow_comparison_uses_last_4_occurrences():
    # 5 Segundas: 2026-04-27, 2026-05-04, 05-11, 05-18, 05-25 → avg das últimas 4
    txs = [
        _tx(10.0, date="2026-04-27"),
        _tx(20.0, date="2026-05-04"),
        _tx(30.0, date="2026-05-11"),
        _tx(40.0, date="2026-05-18"),
        _tx(50.0, date="2026-05-25"),
    ]
    result = dow_weekly_comparison(txs)
    assert result is not None
    assert result["by_dow"]["Segunda"]["avg"] == 35.0  # (20+30+40+50)/4


def test_dow_comparison_excludes_disabled_and_income():
    txs = [
        _tx(500.0, date="2026-06-01"),
        _tx(999.0, date="2026-06-01", isDisabled=True),
        _tx(300.0, date="2026-06-01", type_="GANHO"),
    ]
    result = dow_weekly_comparison(txs)
    assert result is not None
    assert result["by_dow"]["Segunda"]["avg"] == 500.0


def test_dow_comparison_returns_none_on_empty():
    assert dow_weekly_comparison([]) is None
    assert dow_weekly_comparison([_tx(100.0, isDisabled=True)]) is None


# ── monthly_pattern ───────────────────────────────────────────────────────────

def test_monthly_pattern_first_half_only():
    txs = [_tx(100.0, date=f"2026-06-{d:02d}") for d in (3, 10, 15)]
    result = monthly_pattern(txs)
    assert result is not None
    assert result["first_half_pct"] == 100.0
    assert result["second_half_pct"] == 0.0


def test_monthly_pattern_equal_split():
    txs = [
        _tx(200.0, date="2026-06-05"),   # dia 5 → 1ª quinzena
        _tx(200.0, date="2026-06-20"),   # dia 20 → 2ª quinzena
    ]
    result = monthly_pattern(txs)
    assert result is not None
    assert result["first_half_pct"] == 50.0
    assert result["second_half_pct"] == 50.0
    assert result["first_half"] == 200.0
    assert result["second_half"] == 200.0


def test_monthly_pattern_top_days_sorted():
    txs = [
        _tx(300.0, date="2026-06-15"),
        _tx(100.0, date="2026-06-01"),
        _tx( 50.0, date="2026-06-10"),
    ]
    result = monthly_pattern(txs)
    assert result["top_days"][0]["day"] == 15
    assert result["top_days"][0]["value"] == 300.0


def test_monthly_pattern_returns_none_on_empty():
    assert monthly_pattern([]) is None
    assert monthly_pattern([_tx(100.0, isDisabled=True)]) is None


# ── open_installments ─────────────────────────────────────────────────────────

def _inst(current, total, monthly):
    return {"currentInstallment": current, "totalInstallments": total, "installmentValue": monthly}


def test_open_installments_calculates_remaining():
    # 2/6 → 4 restantes a 100 = 400
    txs = [_tx(100.0, installment=_inst(2, 6, 100.0))]
    result = open_installments(txs)
    assert result is not None
    assert result["count"] == 1
    assert result["total_remaining"] == 400.0
    entry = result["entries"][0]
    assert entry["remaining"] == 4
    assert entry["monthly_value"] == 100.0


def test_open_installments_ignores_fully_paid():
    txs = [_tx(50.0, installment=_inst(6, 6, 50.0))]
    assert open_installments(txs) is None


def test_open_installments_sorted_by_remaining_value():
    txs = [
        _tx( 50.0, installment=_inst(1, 3,  50.0)),   # remaining = 2 * 50 = 100
        _tx(200.0, installment=_inst(1, 5, 200.0)),   # remaining = 4 * 200 = 800
    ]
    result = open_installments(txs)
    assert result["total_remaining"] == 900.0
    assert result["entries"][0]["total_remaining"] == 800.0


def test_open_installments_excludes_disabled_and_income():
    txs = [
        _tx(100.0, installment=_inst(1, 5, 100.0)),
        _tx(999.0, isDisabled=True, installment=_inst(1, 10, 999.0)),
        _tx(500.0, type_="GANHO", installment=_inst(1, 3, 500.0)),
    ]
    result = open_installments(txs)
    assert result is not None
    assert result["count"] == 1
    assert result["total_remaining"] == 400.0


def test_open_installments_returns_none_on_empty():
    assert open_installments([]) is None
    assert open_installments([_tx(100.0)]) is None  # sem installment
