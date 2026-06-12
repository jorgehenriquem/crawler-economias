import logging

import requests

from me_crawler import config
from me_crawler.auth import SessionManager

log = logging.getLogger(__name__)


class ApiClient:
    """
    Cliente da API do Minhas Economias.

    Recupera-se sozinho de sessão expirada: em 401, dispara um novo login
    via Playwright e repete a chamada uma vez.
    """

    def __init__(
        self,
        auth: SessionManager | None = None,
        session: requests.Session | None = None,
    ):
        self._auth = auth or SessionManager()
        self._session = session

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = self._auth.get_session()
        return self._session

    def _get(self, url: str, params: dict) -> requests.Response:
        resp = self.session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
        if resp.status_code == 401:
            log.warning("Sessão expirou (401). Renovando login...")
            self._session = self._auth.force_login()
            resp = self.session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp

    def get_transactions(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
        size: int = config.DEFAULT_PAGE_SIZE,
    ) -> list[dict]:
        """
        Busca todas as transações do período, percorrendo a paginação por cursor.

        Na primeira página envia fromDate + toDate; nas seguintes apenas
        toDate=nextCursorDate + cursorId (fromDate cortaria o cursor).
        Para quando hasMore é falso ou o cursor ultrapassa from_date.
        """
        all_transactions: list[dict] = []
        page_num = 0
        cursor_id: int | None = None
        cursor_date: str | None = to_date

        while True:
            page_num += 1
            params: dict = {
                "statuses": config.STATUSES,
                "size": size,
                "sortDirection": "DESC",
            }

            if cursor_id is None:
                if to_date:
                    params["toDate"] = to_date
                if from_date:
                    params["fromDate"] = from_date
            else:
                params["toDate"] = cursor_date
                params["cursorId"] = cursor_id

            data = self._get(config.TRANSACTIONS_URL, params).json()

            transactions = data.get("transactions", [])
            all_transactions.extend(transactions)
            log.info("Página %d: %d transações", page_num, len(transactions))

            has_more = data.get("hasMore", False)
            next_cursor_date = data.get("nextCursorDate")
            next_cursor_id = data.get("nextCursorId")

            if not has_more or not next_cursor_id:
                break

            if from_date and next_cursor_date and next_cursor_date < from_date:
                break

            cursor_id = next_cursor_id
            cursor_date = next_cursor_date

        return all_transactions
