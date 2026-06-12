import csv
import json
import logging
from pathlib import Path

from me_crawler.analytics import brl

log = logging.getLogger(__name__)

CSV_FIELDS = [
    "data",
    "descricao",
    "categoria",
    "subcategoria",
    "valor",
    "tipo",
    "conta",
    "cartao",
    "metodo_pagamento",
    "status",
    "consolidado",
]


def save_json(transactions: list[dict], path: Path) -> Path:
    path.write_text(
        json.dumps(transactions, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    log.info("Salvo em: %s", path)
    return path


def save_csv(transactions: list[dict], path: Path) -> Path:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()

        for t in transactions:
            category = t.get("category") or {}
            sub = t.get("subCategory") or {}
            account = t.get("account") or {}
            card = t.get("creditCard") or {}

            status = "PENDENTE" if t.get("projected") else "CONFIRMADO"
            if t.get("isDisabled"):
                status = "DESABILITADO"

            writer.writerow(
                {
                    "data": t.get("date", ""),
                    "descricao": t.get("description", ""),
                    "categoria": category.get("categoryName", ""),
                    "subcategoria": sub.get("subCategoryName", ""),
                    "valor": t.get("value", 0),
                    "tipo": t.get("type", ""),
                    "conta": account.get("name", ""),
                    "cartao": card.get("name", "") if card else "",
                    "metodo_pagamento": t.get("paymentMethod", ""),
                    "status": status,
                    "consolidado": "Sim" if t.get("isConsolidated") else "Não",
                }
            )

    log.info("Salvo em: %s", path)
    return path


def print_summary(transactions: list[dict], label: str) -> None:
    gastos = sum(t["value"] for t in transactions if t.get("type") == "GASTO")
    ganhos = sum(t["value"] for t in transactions if t.get("type") == "GANHO")
    resultado = ganhos - gastos
    sinal = "-" if resultado < 0 else ""

    print(f"\n=== Resumo: {label} ===")
    print(f"Total de transações: {len(transactions)}")
    print(f"Gastos:    {brl(gastos)}")
    print(f"Ganhos:    {brl(ganhos)}")
    print(f"Resultado: {sinal}{brl(resultado)}\n")
