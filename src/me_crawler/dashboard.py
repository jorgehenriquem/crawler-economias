import logging
from datetime import date
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from me_crawler import analytics
from me_crawler.analytics import (
    COLORS,
    DOW_NAMES,
    METHOD_LABELS,
    analyze,
    brl,
    compare,
    detect_duplicates,
    dow_weekly_comparison,
    monthly_pattern,
    open_installments,
    top_suppliers,
)

log = logging.getLogger(__name__)

_env = Environment(
    loader=PackageLoader("me_crawler", "templates"),
    autoescape=select_autoescape(["html"]),
)
_env.filters["brl"] = brl


def _chart_data(a: dict) -> dict:
    """Extrai da análise as séries prontas para o Chart.js."""
    return {
        "cat_labels": list(a["by_cat"].keys()),
        "cat_values": [round(v, 2) for v in a["by_cat"].values()],
        "cat_colors": COLORS[: len(a["by_cat"])],
        "day_labels": a["days"],
        "day_gastos": a["daily_spending"],
        "day_ganhos": a["daily_ganho"],
        "cumulative": a["cumulative"],
        "ma7": a["ma7"],
        "met_labels": [METHOD_LABELS.get(k, k) for k in a["by_method"]],
        "met_values": [round(v["total"], 2) for v in a["by_method"].values()],
        "met_counts": [v["count"] for v in a["by_method"].values()],
        "met_colors": COLORS[1 : 1 + len(a["by_method"])],
        "acc_labels": list(a["by_account"].keys()),
        "acc_values": [round(v, 2) for v in a["by_account"].values()],
        "acc_colors": COLORS[4 : 4 + len(a["by_account"])],
        "sub_labels": list(a["by_subcat"].keys()),
        "sub_values": [round(v, 2) for v in a["by_subcat"].values()],
        "sub_colors": COLORS[2 : 2 + len(a["by_subcat"])],
    }


def _dow_chart_data(dow_result: dict | None) -> dict:
    if not dow_result:
        return {"labels": [], "avgs": [], "colors": []}
    stats = dow_result["by_dow"]
    labels = [d for d in DOW_NAMES if d in stats]
    avgs = [stats[d]["avg"] for d in labels]
    colors = [
        "#ef4444" if stats[d]["pct_vs_avg"] > 15
        else "#f59e0b" if stats[d]["pct_vs_avg"] > 0
        else "#10b981"
        for d in labels
    ]
    return {"labels": labels, "avgs": avgs, "colors": colors}


def _monthly_chart_data(pattern: dict | None) -> dict:
    if not pattern:
        return {"labels": [], "data": []}
    return {
        "labels": list(pattern["by_day"].keys()),
        "data": list(pattern["by_day"].values()),
    }


def render(
    transactions: list[dict],
    title: str,
    output: Path,
    previous_transactions: list[dict] | None = None,
) -> Path:
    """Gera o dashboard HTML. Se previous_transactions vier, inclui a comparação."""
    a = analyze(transactions)
    comparison = None
    if previous_transactions:
        comparison = compare(a, analytics.analyze(previous_transactions))

    dow = dow_weekly_comparison(transactions)
    duplicates = detect_duplicates(transactions)
    pattern = monthly_pattern(transactions)
    suppliers = top_suppliers(transactions)
    installments = open_installments(transactions)

    html = _env.get_template("dashboard.html").render(
        title=title,
        generated_at=date.today().isoformat(),
        a=a,
        charts=_chart_data(a),
        comparison=comparison,
        method_labels=METHOD_LABELS,
        resultado_color="#10b981" if a["resultado"] >= 0 else "#ef4444",
        resultado_sign="+" if a["resultado"] >= 0 else "−",
        dow=dow,
        dow_chart=_dow_chart_data(dow),
        duplicates=duplicates,
        pattern=pattern,
        monthly_chart=_monthly_chart_data(pattern),
        suppliers=suppliers,
        installments=installments,
    )
    output.write_text(html, encoding="utf-8")
    log.info("Dashboard salvo em: %s", output)
    return output
