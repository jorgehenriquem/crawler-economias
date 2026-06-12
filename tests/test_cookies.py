from me_crawler.auth import SessionManager


def _cookie(name, domain, value="v"):
    return {"name": name, "value": value, "domain": domain, "path": "/"}


def test_filters_foreign_domains():
    session = SessionManager().build_requests_session(
        [
            _cookie("JSESSIONID", "api.minhaseconomias.com.br"),
            _cookie("_GRECAPTCHA", "www.google.com"),
        ]
    )
    names = {c.name for c in session.cookies}
    assert "JSESSIONID" in names
    assert "_GRECAPTCHA" not in names


def test_wildcard_cookies_duplicated_for_subdomains():
    session = SessionManager().build_requests_session([_cookie("cfid", ".minhaseconomias.com.br")])
    domains = {c.domain for c in session.cookies if c.name == "cfid"}
    assert "api.minhaseconomias.com.br" in domains
    assert "portal.minhaseconomias.com.br" in domains


def test_session_has_retry_adapter_and_headers():
    session = SessionManager().build_requests_session([])
    adapter = session.get_adapter("https://api.minhaseconomias.com.br")
    assert adapter.max_retries.total == 3
    assert 503 in adapter.max_retries.status_forcelist
    assert "minhaseconomias" in session.headers["Origin"]
