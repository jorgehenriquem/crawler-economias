# crawler-economias

Ferramenta de linha de comando que extrai transações financeiras do [Minhas Economias](https://portal.minhaseconomias.com.br), persiste em MongoDB e gera dashboards analíticos em HTML.

## Como funciona

O portal não expõe API pública. A autenticação é feita via browser real (Playwright): você loga uma vez, os cookies de sessão são salvos localmente e reutilizados nas execuções seguintes. Com a sessão ativa, o script chama a API interna do site para buscar as transações e as grava no MongoDB com upsert — rodar duas vezes não duplica nada.

## Requisitos

- Python 3.12+
- MongoDB rodando em `localhost:27017`
- WSL Ubuntu (recomendado) ou Linux

## Instalação

```bash
python3 -m venv ~/.venvs/me-crawler
source ~/.venvs/me-crawler/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

## Uso

```bash
me-crawler login                           # autenticação via browser (primeira vez)
me-crawler sync                            # busca últimos 30 dias → MongoDB
me-crawler sync --days 90                  # janela customizada
me-crawler dashboard --open                # dashboard do mês atual no browser
me-crawler dashboard --month 2026-05       # mês específico
me-crawler export --month 2026-06          # exporta CSV + JSON
me-crawler export --format csv             # só CSV
```

No Windows, o `run.bat` encapsula tudo via WSL:

```powershell
.\run.bat sync
.\run.bat dashboard --open
```

## Estrutura

```
src/me_crawler/
├── config.py        # URLs, timeouts, configurações (overrides via env ME_*)
├── auth.py          # login Playwright + persistência de cookies
├── client.py        # chamadas à API com paginação por cursor e auto-recovery
├── store.py         # persistência MongoDB
├── analytics.py     # agregações e comparação entre períodos
├── dashboard.py     # renderização Jinja2
├── exporter.py      # exportação CSV/JSON
├── cli.py           # interface de linha de comando
└── templates/
    └── dashboard.html
tests/
├── test_pagination.py
├── test_analytics.py
└── test_cookies.py
```

## Dashboard

Gerado a partir dos dados do MongoDB, inclui:

- Resumo de gastos, ganhos e resultado do período
- **Filtro por categoria** na barra fixa do topo — atualiza todos os 6 gráficos, KPIs e tabelas em tempo real
- Comparação percentual com o mês anterior por categoria
- Distribuição de gastos por categoria (donut)
- Gastos vs ganhos por dia com média móvel de 7 dias
- Curva de gasto acumulado
- Detalhamento por forma de pagamento, conta e subcategoria
- Padrão de gasto por dia da semana (últimas 4 ocorrências de cada dia)
- Distribuição dos gastos ao longo do mês (1ª vs 2ª quinzena)
- Top fornecedores por volume total gasto
- Parcelas em aberto e total comprometido
- Possíveis cobranças duplicadas (mesmo valor + categoria em ≤ 3 dias)
- Insights: dia mais caro, categoria campeã, dia da semana mais caro, projeção de 30 dias
- Últimas transações com **paginação numerada** (10 por página) e navegação por elipses
- Top 10 maiores gastos (atualizado pelo filtro de categoria)

## Testes

```bash
pytest
```

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `ME_MONGO_URI` | `mongodb://localhost:27017` | URI do MongoDB |
| `ME_MONGO_DB` | `minhas_economias` | Nome do banco |
| `ME_COOKIES_FILE` | `cookies.json` | Caminho do arquivo de sessão |
