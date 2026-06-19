"""Agregações e análises sobre listas de transações."""

from collections import defaultdict
from datetime import datetime

COLORS = [
    "#6366f1",
    "#f59e0b",
    "#10b981",
    "#ef4444",
    "#3b82f6",
    "#8b5cf6",
    "#f97316",
    "#14b8a6",
    "#ec4899",
    "#84cc16",
    "#06b6d4",
    "#a855f7",
    "#f43f5e",
    "#22c55e",
    "#eab308",
]

METHOD_LABELS = {
    "CARD": "Cartão de Crédito",
    "DEBIT": "Débito",
    "MONEY": "Dinheiro",
    "PIX": "Pix",
    "TED": "TED",
    "BOLETO": "Boleto",
    "TRANSFER": "Transferência",
}

DOW_NAMES = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def brl(v: float) -> str:
    return f"R$ {abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def analyze(txs: list[dict]) -> dict:
    """Calcula totais, agregações por dimensão e séries temporais de um período."""
    active = [t for t in txs if not t.get("isDisabled")]
    gastos = [t for t in active if t.get("type") == "GASTO"]
    ganhos = [t for t in active if t.get("type") == "GANHO"]

    total_gastos = sum(t["value"] for t in gastos)
    total_ganhos = sum(t["value"] for t in ganhos)

    by_cat: dict[str, float] = defaultdict(float)
    for t in gastos:
        by_cat[(t.get("category") or {}).get("categoryName", "Outros")] += t["value"]
    by_cat = dict(sorted(by_cat.items(), key=lambda x: x[1], reverse=True))

    by_day: dict[str, float] = defaultdict(float)
    for t in gastos:
        by_day[t.get("date", "?")] += t["value"]
    by_day = dict(sorted(by_day.items()))

    by_day_ganho: dict[str, float] = defaultdict(float)
    for t in ganhos:
        by_day_ganho[t.get("date", "?")] += t["value"]

    days = sorted(by_day.keys())
    daily_spending = [round(by_day[d], 2) for d in days]

    cumulative, running = [], 0.0
    for v in daily_spending:
        running += v
        cumulative.append(round(running, 2))

    # Média móvel de 7 dias sobre a série diária
    ma7 = []
    for i in range(len(daily_spending)):
        window = daily_spending[max(0, i - 6) : i + 1]
        ma7.append(round(sum(window) / len(window), 2))

    by_method: dict = defaultdict(lambda: {"count": 0, "total": 0.0})
    for t in gastos:
        m = t.get("paymentMethod") or "OUTRO"
        by_method[m]["count"] += 1
        by_method[m]["total"] = round(by_method[m]["total"] + t["value"], 2)
    by_method = dict(sorted(by_method.items(), key=lambda x: x[1]["total"], reverse=True))

    by_account: dict[str, float] = defaultdict(float)
    for t in gastos:
        by_account[(t.get("account") or {}).get("name", "Sem conta")] += t["value"]
    by_account = dict(sorted(by_account.items(), key=lambda x: x[1], reverse=True))

    by_subcat: dict[str, float] = defaultdict(float)
    for t in gastos:
        sub = (t.get("subCategory") or {}).get("subCategoryName") or (t.get("category") or {}).get(
            "categoryName", "Outros"
        )
        by_subcat[sub] += t["value"]
    by_subcat = dict(sorted(by_subcat.items(), key=lambda x: x[1], reverse=True)[:8])

    dow: dict[str, float] = defaultdict(float)
    for t in gastos:
        try:
            d = datetime.strptime(t["date"], "%Y-%m-%d")
            dow[DOW_NAMES[d.weekday()]] += t["value"]
        except (ValueError, KeyError):
            pass

    ticket_medio = total_gastos / len(gastos) if gastos else 0.0
    dia_mais_caro = max(by_day.items(), key=lambda x: x[1]) if by_day else ("—", 0.0)
    top_cat = next(iter(by_cat.items())) if by_cat else ("—", 0.0)
    top_cat_pct = top_cat[1] / total_gastos * 100 if total_gastos else 0.0
    busiest_dow = max(dow.items(), key=lambda x: x[1]) if dow else ("—", 0.0)

    projected = None
    if len(days) >= 2:
        try:
            first = datetime.strptime(days[0], "%Y-%m-%d")
            last = datetime.strptime(days[-1], "%Y-%m-%d")
            n_days = max((last - first).days + 1, 1)
            projected = total_gastos / n_days * 30
        except ValueError:
            pass

    top10 = sorted(gastos, key=lambda x: x["value"], reverse=True)[:10]
    recent = sorted(active, key=lambda x: x.get("date", ""), reverse=True)

    return {
        "total_gastos": total_gastos,
        "total_ganhos": total_ganhos,
        "resultado": total_ganhos - total_gastos,
        "n_transacoes": len(active),
        "n_gastos": len(gastos),
        "n_ganhos": len(ganhos),
        "ticket_medio": ticket_medio,
        "dia_mais_caro": dia_mais_caro,
        "top_cat": top_cat,
        "top_cat_pct": top_cat_pct,
        "busiest_dow": busiest_dow,
        "projected": projected,
        "by_cat": by_cat,
        "days": days,
        "daily_spending": daily_spending,
        "daily_ganho": [round(by_day_ganho.get(d, 0), 2) for d in days],
        "cumulative": cumulative,
        "ma7": ma7,
        "by_method": by_method,
        "by_account": by_account,
        "by_subcat": by_subcat,
        "top10": top10,
        "recent": recent,
    }


def dow_weekly_comparison(txs: list[dict]) -> dict | None:
    """
    Para cada dia da semana, calcula o gasto médio nas últimas 4 ocorrências
    e o percentual acima/abaixo da média geral — revela dias consistentemente caros.
    """
    gastos = [t for t in txs if t.get("type") == "GASTO" and not t.get("isDisabled")]

    by_date: dict[str, float] = defaultdict(float)
    for t in gastos:
        by_date[t.get("date", "?")] += t["value"]

    dow_values: dict[str, list[float]] = defaultdict(list)
    for date_str, total in sorted(by_date.items()):
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            dow_values[DOW_NAMES[d.weekday()]].append(total)
        except ValueError:
            pass

    if not dow_values:
        return None

    dow_stats: dict[str, dict] = {}
    for dow in DOW_NAMES:
        if dow not in dow_values:
            continue
        vals = dow_values[dow][-4:]
        avg = sum(vals) / len(vals)
        dow_stats[dow] = {"avg": round(avg, 2), "weeks": [round(v, 2) for v in vals], "n": len(vals)}

    if not dow_stats:
        return None

    overall = sum(v["avg"] for v in dow_stats.values()) / len(dow_stats)
    for data in dow_stats.values():
        data["pct_vs_avg"] = round((data["avg"] - overall) / overall * 100, 1) if overall else 0.0

    worst = max(dow_stats.items(), key=lambda x: x[1]["avg"])
    max_avg = worst[1]["avg"]
    return {
        "by_dow": dow_stats,
        "overall_daily_avg": round(overall, 2),
        "most_expensive": worst[0],
        "most_expensive_pct": worst[1]["pct_vs_avg"],
        "max_avg": max_avg,
    }


def detect_duplicates(txs: list[dict], days_window: int = 3) -> list[dict]:
    """
    Detecta pares de gastos com mesmo valor e mesma categoria em datas próximas.
    Útil para identificar cobranças duplicadas ou compras esquecidas.
    """
    gastos = sorted(
        [t for t in txs if t.get("type") == "GASTO" and not t.get("isDisabled")],
        key=lambda x: x.get("date", ""),
    )

    suspected: list[dict] = []
    seen_uuids: set[tuple] = set()

    for i, t in enumerate(gastos):
        cat = (t.get("category") or {}).get("categoryName", "")
        val = t.get("value", 0)
        try:
            d = datetime.strptime(t.get("date", ""), "%Y-%m-%d")
        except ValueError:
            continue

        for prev in gastos[:i]:
            prev_cat = (prev.get("category") or {}).get("categoryName", "")
            prev_val = prev.get("value", 0)
            try:
                prev_d = datetime.strptime(prev.get("date", ""), "%Y-%m-%d")
            except ValueError:
                continue

            if abs((d - prev_d).days) > days_window:
                continue
            if val != prev_val or cat != prev_cat:
                continue

            pair = tuple(sorted([t.get("uuid", ""), prev.get("uuid", "")]))
            if pair in seen_uuids:
                continue
            seen_uuids.add(pair)
            suspected.append({
                "tx_a": prev,
                "tx_b": t,
                "value": val,
                "category": cat,
                "days_apart": abs((d - prev_d).days),
            })

    return suspected


def monthly_pattern(txs: list[dict]) -> dict | None:
    """
    Mostra como os gastos se distribuem ao longo dos dias do mês —
    revela se você gasta mais no começo, no meio ou no final do mês.
    """
    gastos = [t for t in txs if t.get("type") == "GASTO" and not t.get("isDisabled")]

    by_day_num: dict[int, float] = defaultdict(float)
    for t in gastos:
        try:
            by_day_num[datetime.strptime(t["date"], "%Y-%m-%d").day] += t["value"]
        except (ValueError, KeyError):
            pass

    if not by_day_num:
        return None

    first_half = sum(v for k, v in by_day_num.items() if k <= 15)
    second_half = sum(v for k, v in by_day_num.items() if k > 15)
    total = first_half + second_half or 1

    sorted_days = sorted(by_day_num.items())
    top_days = sorted(by_day_num.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "first_half": round(first_half, 2),
        "second_half": round(second_half, 2),
        "first_half_pct": round(first_half / total * 100, 1),
        "second_half_pct": round(second_half / total * 100, 1),
        "by_day": {str(k): round(v, 2) for k, v in sorted_days},
        "top_days": [{"day": d, "value": round(v, 2)} for d, v in top_days],
        "peak_day": top_days[0][0] if top_days else 0,
        "peak_value": round(top_days[0][1], 2) if top_days else 0,
    }


def top_suppliers(txs: list[dict], n: int = 15) -> list[dict]:
    """
    Agrupa gastos por descrição normalizada para identificar os fornecedores
    onde mais dinheiro é gasto — base para negociação ou troca de hábito.
    """
    import re

    gastos = [t for t in txs if t.get("type") == "GASTO" and not t.get("isDisabled")]

    suppliers: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0, "category": ""})
    for t in gastos:
        raw = (t.get("description") or "SEM DESCRIÇÃO").strip().upper()
        name = re.sub(r"\s+\d+$", "", raw).strip()  # remove código de loja no final
        suppliers[name]["total"] = round(suppliers[name]["total"] + t["value"], 2)
        suppliers[name]["count"] += 1
        if not suppliers[name]["category"]:
            suppliers[name]["category"] = (t.get("category") or {}).get("categoryName", "—")

    return sorted(
        [
            {
                "name": name,
                "total": data["total"],
                "count": data["count"],
                "avg_ticket": round(data["total"] / data["count"], 2),
                "category": data["category"],
            }
            for name, data in suppliers.items()
        ],
        key=lambda x: x["total"],
        reverse=True,
    )[:n]


def open_installments(txs: list[dict]) -> dict | None:
    """
    Calcula quanto das compras parceladas já está comprometido para os próximos meses.
    """
    parceladas = [
        t for t in txs
        if t.get("installment") and t.get("type") == "GASTO" and not t.get("isDisabled")
    ]
    if not parceladas:
        return None

    def _extract(inst: dict) -> tuple[int, int] | None:
        current = inst.get("currentInstallment") or inst.get("current") or inst.get("number")
        total = inst.get("totalInstallments") or inst.get("total")
        if current and total:
            return int(current), int(total)
        return None

    items = []
    total_remaining = 0.0

    for t in parceladas:
        inst = t.get("installment")
        if not isinstance(inst, dict):
            continue
        info = _extract(inst)
        if not info:
            continue
        current, total_inst = info
        remaining = total_inst - current
        if remaining <= 0:
            continue
        monthly = inst.get("installmentValue") or inst.get("value") or t.get("value", 0)
        remaining_value = remaining * float(monthly)
        total_remaining += remaining_value
        items.append({
            "description": t.get("description", "—"),
            "category": (t.get("category") or {}).get("categoryName", "—"),
            "current": current,
            "total": total_inst,
            "remaining": remaining,
            "monthly_value": round(float(monthly), 2),
            "total_remaining": round(remaining_value, 2),
        })

    if not items:
        return None

    return {
        "entries": sorted(items, key=lambda x: x["total_remaining"], reverse=True)[:10],
        "total_remaining": round(total_remaining, 2),
        "count": len(items),
    }


def compare(current: dict, previous: dict) -> dict | None:
    """
    Compara duas análises (analyze()) — tipicamente mês atual vs anterior.
    Retorna None se o período anterior não tem gastos.
    """
    if not previous or previous["total_gastos"] == 0:
        return None

    cur_total = current["total_gastos"]
    prev_total = previous["total_gastos"]
    delta_pct = (cur_total - prev_total) / prev_total * 100

    rows = []
    cats = list(current["by_cat"].keys())
    cats += [c for c in previous["by_cat"] if c not in cats]
    for cat in cats[:8]:
        cur_v = current["by_cat"].get(cat, 0.0)
        prev_v = previous["by_cat"].get(cat, 0.0)
        row_delta = ((cur_v - prev_v) / prev_v * 100) if prev_v > 0 else None
        rows.append(
            {
                "category": cat,
                "current": cur_v,
                "previous": prev_v,
                "delta_pct": row_delta,
            }
        )

    return {
        "prev_total": prev_total,
        "delta_pct": delta_pct,
        "rows": rows,
    }
