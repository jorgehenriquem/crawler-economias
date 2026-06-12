import logging
from datetime import UTC, datetime

from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError

from me_crawler import config

log = logging.getLogger(__name__)


class StoreUnavailableError(RuntimeError):
    """MongoDB inacessível."""


class TransactionStore:
    """
    Persistência das transações no MongoDB.

    Transações são identificadas pelo uuid da API: sincronizar duas vezes
    não duplica nada, e edições feitas no site sobrescrevem o documento.
    """

    def __init__(self, uri: str = config.MONGO_URI, db_name: str = config.MONGO_DB):
        self._client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        try:
            self._client.admin.command("ping")
        except PyMongoError as exc:
            raise StoreUnavailableError(
                f"MongoDB inacessível em {uri}. O serviço está rodando?"
            ) from exc

        db = self._client[db_name]
        self.transactions = db["transactions"]
        self.sync_runs = db["sync_runs"]
        self.transactions.create_index("uuid", unique=True)
        self.transactions.create_index("date")

    def upsert_transactions(self, transactions: list[dict]) -> dict:
        """Upsert em lote por uuid. Retorna contagens {fetched, new, updated}."""
        if not transactions:
            return {"fetched": 0, "new": 0, "updated": 0}

        ops = [
            UpdateOne({"uuid": t["uuid"]}, {"$set": t}, upsert=True)
            for t in transactions
            if t.get("uuid")
        ]
        result = self.transactions.bulk_write(ops, ordered=False)
        return {
            "fetched": len(transactions),
            "new": result.upserted_count,
            "updated": result.modified_count,
        }

    def record_sync(self, from_date: str, to_date: str, counts: dict) -> None:
        self.sync_runs.insert_one(
            {
                "at": datetime.now(UTC),
                "from_date": from_date,
                "to_date": to_date,
                **counts,
            }
        )

    def last_sync(self) -> dict | None:
        return self.sync_runs.find_one(sort=[("at", -1)])

    def get_range(self, from_date: str, to_date: str) -> list[dict]:
        """Transações com date entre from_date e to_date (inclusive), sem o _id."""
        return list(
            self.transactions.find(
                {"date": {"$gte": from_date, "$lte": to_date}},
                projection={"_id": False},
            ).sort("date", -1)
        )

    def get_all(self) -> list[dict]:
        """Todas as transações disponíveis no banco, sem filtro de data."""
        return list(self.transactions.find({}, projection={"_id": False}).sort("date", -1))

    def get_month(self, year: int, month: int) -> list[dict]:
        import calendar

        last_day = calendar.monthrange(year, month)[1]
        return self.get_range(
            f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"
        )
