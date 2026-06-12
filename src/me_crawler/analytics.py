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
