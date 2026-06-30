"""Tests for document classification heuristics."""

from app.classifiers.document import classify_document


def test_classify_nfse_sp():
    text = "PREFEITURA DO MUNICÍPIO DE SÃO PAULO\nNOTA FISCAL ELETRÔNICA DE SERVIÇOS - NFS-e"
    result = classify_document(text)
    assert result.category == "nfse"
    assert result.subtype == "nfse_sp"


def test_classify_danfe():
    text = "DANFE\nDOCUMENTO AUXILIAR DA NOTA FISCAL ELETRÔNICA\nCHAVE DE ACESSO"
    result = classify_document(text)
    assert result.category == "nfe"
    assert result.subtype == "danfe"


def test_classify_sabesp():
    text = "Fatura de Serviços de Água e/ou Esgotos\nSabesp"
    result = classify_document(text)
    assert result.category == "utility_water"
    assert result.subtype == "sabesp"


def test_classify_enel():
    text = (
        "Eletropaulo Metropolitana\n"
        "NOTA FISCAL Nº 000054765 - Série 001\n"
        "kWh\nPREFEITURA DO MUNICÍPIO 0800"
    )
    result = classify_document(text)
    assert result.category == "nf3e"
    assert result.subtype == "enel"


def test_classify_vivo():
    text = "Telefonica Brasil S.A.\nwww.vivo.com.br/meuvivoempresas\nSMART EMPRESAS"
    result = classify_document(text)
    assert result.category == "utility_telecom"
    assert result.subtype == "vivo"


def test_classify_rental():
    text = "FATURA/DUPLICATA\nLOCACAO DE EQUIPAMENTOS - KIT ESP. CONFINADO"
    result = classify_document(text)
    assert result.category == "rental_invoice"


def test_classify_vai_locar_nota_debito():
    text = (
        "NOTA DE DEBITO\n"
        "VAI LOCAR EQUIPAMENTOS LTDA\n"
        "LOCAÇÃO DE EQUIPAMENTOS CONFORME CONTRATO\n"
        "CGNFSe e LC 214/2025"
    )
    result = classify_document(text)
    assert result.category == "rental_invoice"
    assert result.subtype == "nota_debito"


def test_classify_hint_override():
    text = "documento genérico sem padrão claro"
    result = classify_document(text, hint_type="utility_water")
    assert result.category == "utility_water"


def test_cgnfse_does_not_trigger_nfse():
    text = "Operação tributada CGNFSe LC 214/2025 locação"
    result = classify_document(text)
    assert result.category != "nfse"
