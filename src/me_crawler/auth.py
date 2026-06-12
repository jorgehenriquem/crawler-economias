import json
import logging
import time

import requests
from playwright.sync_api import sync_playwright
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from me_crawler import config

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class SessionManager:
    def login_with_playwright(self) -> list[dict]:
        """
        Abre browser visível e aguarda o usuário fazer login.
        Considera a sessão estabelecida quando o browser faz chamadas reais à API.
        Salva e retorna a lista de cookies do Playwright.
        """
        log.info("Abrindo browser para login... (timeout: 2 minutos)")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            api_calls: list[str] = []

            def on_response(response):
                if "api.minhaseconomias.com.br" in response.url:
                    api_calls.append(response.url)

            context.on("response", on_response)
            page.goto(config.LOGIN_URL)

            log.info("Faça login no browser. O script detecta automaticamente quando entrar.")

            deadline = time.time() + config.LOGIN_TIMEOUT_MS / 1000
            authenticated = False
            while time.time() < deadline:
                try:
                    url = page.url
                    on_portal = "minhaseconomias.com.br" in url and "/login" not in url
                    if on_portal and api_calls:
                        authenticated = True
                        break
                except Exception:
                    pass
                time.sleep(1)

            if not authenticated:
                log.warning("Timeout aguardando login. Capturando cookies mesmo assim.")
            else:
                log.info("Sessão detectada (%d chamadas API).", len(api_calls))

            time.sleep(3)  # buffer para cookies httpOnly propagarem
            playwright_cookies = context.cookies()
            browser.close()

        self._save_cookies(playwright_cookies)
        return playwright_cookies

    def _save_cookies(self, cookies: list[dict]) -> None:
        config.COOKIES_FILE.write_text(
            json.dumps(cookies, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log.info("Sessão salva em %s", config.COOKIES_FILE)

    def load_cookies(self) -> list[dict]:
        return json.loads(config.COOKIES_FILE.read_text(encoding="utf-8"))

    def is_session_valid(self, session: requests.Session) -> bool:
        """POST /session/alive — True se a sessão ainda é aceita pela API."""
        try:
            resp = session.post(config.SESSION_ALIVE_URL, json={}, timeout=config.REQUEST_TIMEOUT)
            if resp.status_code == 200:
                body = resp.json() if resp.content else {}
                return body.get("result", True)
            return False
        except requests.RequestException as exc:
            log.debug("Erro ao verificar sessão: %s", exc)
            return False

    def build_requests_session(self, playwright_cookies: list[dict]) -> requests.Session:
        """
        Converte cookies do Playwright para um requests.Session com retry automático
        (backoff exponencial em 502/503/504).
        """
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Origin": config.PORTAL_URL,
                "Referer": config.PORTAL_URL + "/",
            }
        )

        retry = Retry(
            total=3,
            backoff_factor=1.5,
            status_forcelist=[502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        jar = requests.cookies.RequestsCookieJar()
        for ck in playwright_cookies:
            domain = ck.get("domain", "")
            if "minhaseconomias.com.br" not in domain:
                continue

            name, value, path = ck["name"], ck["value"], ck.get("path", "/")
            jar.set(name, value, domain=domain, path=path)

            # Cookies wildcard (.minhaseconomias.com.br) precisam ser setados
            # explicitamente nos subdomínios — o requests não faz o match
            # de subdomínio da mesma forma que o browser.
            if domain.startswith("."):
                jar.set(name, value, domain="api.minhaseconomias.com.br", path=path)
                jar.set(name, value, domain="portal.minhaseconomias.com.br", path=path)

        session.cookies = jar
        return session

    def get_session(self) -> requests.Session:
        """
        Retorna um requests.Session autenticado.
        Reutiliza cookies salvos se a sessão ainda for válida; senão abre o browser.
        """
        if config.COOKIES_FILE.exists():
            session = self.build_requests_session(self.load_cookies())
            if self.is_session_valid(session):
                log.info("Sessão válida carregada de %s", config.COOKIES_FILE)
                return session
            log.info("Sessão expirada. Iniciando novo login.")
        else:
            log.info("Nenhuma sessão salva encontrada.")

        return self.force_login()

    def force_login(self) -> requests.Session:
        """Força novo login via Playwright, independente de cookies salvos."""
        cookies = self.login_with_playwright()
        return self.build_requests_session(cookies)
