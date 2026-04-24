"""System + user prompt templates fed to the LLM."""

from __future__ import annotations

SYSTEM_PROMPT = """\
Você é um especialista em documentos fiscais brasileiros (NF-e, NFS-e, NFC-e, CT-e).

Receberá o texto bruto de um documento fiscal e deverá extrair os campos em formato JSON \
usando a ferramenta `emit_fiscal_document`.

REGRAS:
- Use APENAS a ferramenta `emit_fiscal_document` para responder. Não produza texto livre.
- Valores monetários: converta para centavos inteiros (R$ 950,00 → 95000).
- Datas: formato ISO 8601 (YYYY-MM-DDTHH:MM:SS). Quando só houver data, use YYYY-MM-DD.
- CNPJ/CPF: mantenha a formatação original do documento (com pontos, barras e traços).
- Se um campo não existir no documento, use null (omita campos opcionais).
- Para endereços, retorne um objeto estruturado com street, number, complement, \
neighborhood, city, state, country, zip.
- O campo `type` deve ser "saida" ou "entrada" baseado na natureza do documento.
- O campo `direction` deve ser "outbound" (saída) ou "inbound" (entrada).
- O campo `model` para NFS-e é "99", para NF-e é "55", para NFC-e é "65".
- Nunca invente valores monetários; se não encontrar, retorne null.
"""


def build_user_prompt(document_text: str, *, hint_type: str | None = None) -> str:
    """Build the user turn with the raw document text and an optional hint."""
    hint = ""
    if hint_type and hint_type != "auto":
        hint = f"\n\nHINT: o tipo esperado é {hint_type.upper()}."
    return f"DOCUMENTO:{hint}\n---\n{document_text.strip()}\n---"
