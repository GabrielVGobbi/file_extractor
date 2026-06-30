# Fiscal Document Extractor API

Serviço HTTP standalone em FastAPI que recebe **qualquer documento brasileiro** relevante para controladoria fiscal (PDF, imagem, XML, DOCX) e devolve um JSON estruturado pronto para inserção no ERP.

## Tipos suportados

| Categoria | Exemplos |
|---|---|
| `nfe`, `nfce`, `cte` | DANFE, XML NF-e |
| `nfse` | NFS-e (SP, ABRASF, etc.) |
| `nf3e` | Conta de energia (Enel/Eletropaulo) |
| `utility_water` | Sabesp, saneamento |
| `utility_electricity` | CEMIG, CPFL, Light |
| `utility_telecom` | Vivo, Claro, TIM, Oi |
| `utility_gas` | Comgás |
| `rental_invoice` | Fatura de locação de equipamentos |
| `boleto`, `invoice`, `receipt` | Cobranças e faturas genéricas |

## Estrutura do JSON

Além dos campos planos da tabela `fiscal_documents`, a resposta inclui:

- **`parties`** — emitente, destinatário, pagador, beneficiário
- **`line_items`** — produtos, serviços, rubricas de faturamento
- **`withholdings`** — retenções (ISS, IRRF, INSS, PIS, COFINS, CSLL)
- **`taxes`** — detalhamento de impostos (base, alíquota, valor)
- **`payment`** — boleto, PIX, linha digitável, vencimento, banco
- **`consumption`** — consumo (kWh, m³, GB), medidor, leituras
- **`billing`** — período de referência, emissão, apresentação

Pipeline: extração de texto → **markdown** → LLM classifica e estrutura → validação Pydantic → JSON.

Camadas sem LLM (custo zero): cache, XML NF-e/NFS-e, heurística NFS-e SP/ABRASF.

O classificador regex (`suggest_category`) é **apenas advisory** — log/debug, não influencia a IA.

> **XML NF-e / NFS-e ABRASF** NÃO passa pelo LLM — parser lxml determinístico com `confidence = 1.0` e custo zero.

---

## Requisitos

- Python 3.11+
- Tesseract OCR (binário nativo) com idioma português
- Poppler (para `pdf2image`)
- Redis (opcional, apenas se `ENABLE_CELERY=true`)
- Conta Anthropic com API key

---

## Quickstart — desenvolvimento (Windows / Laragon)

### 1. Instalar binários nativos

- **Tesseract**: baixe o instalador [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki). Durante a instalação, marque o pacote de linguagem **Portuguese**.
- **Poppler**: baixe o zip de [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases), extraia e aponte `POPPLER_PATH` para a pasta `Library\bin`.

### 2. Criar venv e instalar dependências

```powershell
cd fiscal-extractor
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

### 3. Configurar `.env`

```powershell
copy .env.example .env
# edite .env e preencha ANTHROPIC_API_KEY, JWT_SECRET, TESSERACT_CMD, POPPLER_PATH
```

### 4. Rodar a API

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 1000
```

Docs interativas em `http://localhost:8000/docs`.

### 5. Gerar um token JWT de teste

python -m venv

Com o `venv` ativo e `.env` configurado, execute:

```powershell
.\.venv\Scripts\python.exe .\scripts\issue_token.py --header
```

Isso imprime um header no formato:

```powershell
Authorization: Bearer <seu-jwt>
```

Se preferir apenas o valor do token:

```powershell
$TOKEN = python .\scripts\issue_token.py
```

### 6. Smoke test

```powershell
curl.exe -X POST http://localhost:8000/api/v1/extract `
  -H "Authorization: Bearer $TOKEN" `
  -F "file=@tests/fixtures/nfse_sample.pdf" `
  -F "document_type=nfse"
```

---

## Quickstart — produção (Digital Ocean + Docker)

Veja o guia completo em [docs/DEPLOY_DIGITAL_OCEAN.md](docs/DEPLOY_DIGITAL_OCEAN.md). Resumo:

```bash
# No droplet
git clone <repo> && cd fiscal-extractor
cp .env.example .env && nano .env
docker compose up -d --build
```

---

## Rotas

| Método | Path | Descrição |
|---|---|---|
| POST | `/api/v1/extract` | Extrai dados de um documento fiscal. Use `async=true` para dispatch via Celery. |
| GET  | `/api/v1/jobs/{job_id}` | Consulta status de um job assíncrono. |
| GET  | `/health` | Liveness (sempre 200). |
| GET  | `/health/ready` | Readiness (checa configuração do LLM e OCR). |

---

## Testes

```powershell
pytest
```

Analisar os PDFs de exemplo (classificação + preview):

```powershell
python scripts/analyze_examples.py
```

---

## Licença

Uso interno ORC-Tesseract.



cd /var/www/html/fiscal-extractor

git pull
source .venv/bin/activate
pip install -r requirements.txt

rm -rf .cache/extractions

sudo systemctl restart fiscal-api
sudo systemctl restart fiscal-worker

sudo systemctl status fiscal-api --no-pager
sudo systemctl status fiscal-worker --no-pager

curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/health/ready