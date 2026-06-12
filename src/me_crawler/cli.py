"""
CLI do Minhas Economias Crawler.

Comandos:
  me-crawler login                          força novo login via browser
  me-crawler sync [--days 30]               busca transações → MongoDB
  me-crawler dashboard [--month YYYY-MM] [--open]
  me-crawler export [--month YYYY-MM] [--format csv|json|both]
"""

import argparse
import logging
import shutil
import subprocess
import sys
import webbrowser
from datetime import date, timedelta
from pathlib import Path

from me_crawler import config
from me_crawler.auth import SessionManager
from me_crawler.client import ApiClient
from me_crawler.exporter import print_summary, save_csv, save_json
from me_crawler.store import StoreUnavailableError, TransactionStore

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _parse_month(value: str | None) -> tuple[int, int]:
    """'YYYY-MM' → (year, month). Default: mês atual."""
    if not value:
        today = date.today()
        return today.year, today.month
    try:
        year, month = value.split("-")
        return int(year), int(month)
    except ValueError:
        raise SystemExit(f"Mês inválido: {value!r}. Use o formato YYYY-MM, ex: 2026-06.") from None


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _open_in_browser(path: Path) -> None:
    """Abre o arquivo no browser do Windows (quando rodando no WSL) ou no padrão do SO."""
    resolved = path.resolve()
    if shutil.which("wslpath") and shutil.which("explorer.exe"):
        win_path = subprocess.run(
            ["wslpath", "-w", str(resolved)], capture_output=True, text=True
        ).stdout.strip()
        subprocess.run(["explorer.exe", win_path])
    else:
        webbrowser.open(resolved.as_uri())


def cmd_login(_args) -> None:
    SessionManager().force_login()
    log.info("Login concluído e sessão salva.")


def cmd_sync(args) -> None:
    store = TransactionStore()
    to_date = date.today()
    from_date = to_date - timedelta(days=args.days)

    log.info("Sincronizando %s a %s...", from_date.isoformat(), to_date.isoformat())
    client = ApiClient()
    transactions = client.get_transactions(
        from_date=from_date.isoformat(), to_date=to_date.isoformat()
    )

    counts = store.upsert_transactions(transactions)
    store.record_sync(from_date.isoformat(), to_date.isoformat(), counts)

    log.info(
        "Sync concluído: %d buscadas, %d novas, %d atualizadas.",
        counts["fetched"],
        counts["new"],
        counts["updated"],
    )
    print_summary(transactions, f"{from_date.isoformat()} a {to_date.isoformat()}")


def cmd_dashboard(args) -> None:
    from me_crawler import dashboard  # import tardio: jinja2 só é necessária aqui

    store = TransactionStore()

    if args.all:
        transactions = store.get_all()
        if not transactions:
            raise SystemExit("Nenhuma transação no banco. Rode: me-crawler sync")
        title = "Histórico completo"
        output = Path("dashboard_all.html")
        dashboard.render(transactions, title, output)
    else:
        year, month = _parse_month(args.month)
        transactions = store.get_month(year, month)

        if not transactions:
            last = store.last_sync()
            hint = (
                f"Último sync: {last['at']:%Y-%m-%d %H:%M} ({last['from_date']} a {last['to_date']})."
                if last
                else "Nenhum sync registrado ainda."
            )
            raise SystemExit(
                f"Sem transações para {year:04d}-{month:02d} no banco. {hint} Rode: me-crawler sync"
            )

        prev_year, prev_month = _previous_month(year, month)
        previous = store.get_month(prev_year, prev_month)

        title = f"Mês {year:04d}-{month:02d}"
        output = Path(f"dashboard_{year:04d}-{month:02d}.html")
        dashboard.render(transactions, title, output, previous_transactions=previous or None)

    print_summary(transactions, title)

    if args.open:
        _open_in_browser(output)


def cmd_export(args) -> None:
    store = TransactionStore()
    year, month = _parse_month(args.month)
    transactions = store.get_month(year, month)

    if not transactions:
        raise SystemExit(
            f"Sem transações para {year:04d}-{month:02d} no banco. Rode: me-crawler sync"
        )

    stem = f"transactions_{year:04d}-{month:02d}"
    if args.format in ("json", "both"):
        save_json(transactions, Path(f"{stem}.json"))
    if args.format in ("csv", "both"):
        save_csv(transactions, Path(f"{stem}.csv"))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="me-crawler",
        description="Crawler do Minhas Economias: sync para MongoDB + dashboard HTML",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Força novo login via browser").set_defaults(func=cmd_login)

    p_sync = sub.add_parser("sync", help="Busca transações e grava no MongoDB")
    p_sync.add_argument(
        "--days",
        type=int,
        default=config.DEFAULT_SYNC_DAYS,
        help=f"Quantos dias para trás sincronizar (padrão: {config.DEFAULT_SYNC_DAYS})",
    )
    p_sync.set_defaults(func=cmd_sync)

    p_dash = sub.add_parser("dashboard", help="Gera dashboard HTML a partir do MongoDB")
    p_dash.add_argument("--month", help="Mês no formato YYYY-MM (padrão: mês atual)")
    p_dash.add_argument("--all", action="store_true", help="Usa todo o histórico disponível no banco")
    p_dash.add_argument("--open", action="store_true", help="Abre o HTML no browser")
    p_dash.set_defaults(func=cmd_dashboard)

    p_exp = sub.add_parser("export", help="Exporta transações do MongoDB para CSV/JSON")
    p_exp.add_argument("--month", help="Mês no formato YYYY-MM (padrão: mês atual)")
    p_exp.add_argument("--format", choices=["csv", "json", "both"], default="both")
    p_exp.set_defaults(func=cmd_export)

    args = parser.parse_args()
    try:
        args.func(args)
    except StoreUnavailableError as exc:
        log.error("%s", exc)
        sys.exit(2)


if __name__ == "__main__":
    main()
