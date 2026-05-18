# Fiscal Document Extractor API

Serviço HTTP standalone em FastAPI que recebe documentos fiscais brasileiros (PDF, imagem, XML, DOCX) e devolve um JSON estruturado pronto para inserção na tabela `fiscal_documents` do ERP Laravel.

Pipeline: detecção de tipo → extração (pymupdf / OCR / lxml / python-docx) → LLM (Claude) para normalização semântica → validação Pydantic + confidence scoring → JSON.

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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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

---

## Licença

Uso interno ORC-Tesseract.
