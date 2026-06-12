import logging
from datetime import date
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from me_crawler import analytics
from me_crawler.analytics import COLORS, METHOD_LABELS, analyze, brl, compare

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

    html = _env.get_template("dashboard.html").render(
        title=title,
        generated_at=date.today().isoformat(),
        a=a,
        charts=_chart_data(a),
        comparison=comparison,
        method_labels=METHOD_LABELS,
        resultado_color="#10b981" if a["resultado"] >= 0 else "#ef4444",
        resultado_sign="+" if a["resultado"] >= 0 else "−",
    )
    output.write_text(html, encoding="utf-8")
    log.info("Dashboard salvo em: %s", output)
    return output
