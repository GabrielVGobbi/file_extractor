"""Validation helpers for CNPJ, CPF and NF-e / NFS-e access keys."""

from __future__ import annotations

import re

_DIGITS = re.compile(r"\D+")


def only_digits(value: str | None) -> str:
    if value is None:
        return ""
    return _DIGITS.sub("", value)


def is_valid_cnpj(value: str | None) -> bool:
    digits = only_digits(value)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    return digits[-2:] == _cnpj_checksum(digits[:12])


def is_valid_cpf(value: str | None) -> bool:
    digits = only_digits(value)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    return digits[-2:] == _cpf_checksum(digits[:9])


def is_valid_document(value: str | None) -> bool:
    """Accepts CNPJ or CPF."""
    digits = only_digits(value)
    if len(digits) == 14:
        return is_valid_cnpj(value)
    if len(digits) == 11:
        return is_valid_cpf(value)
    return False


def is_valid_nfe_access_key(value: str | None) -> bool:
    """NF-e chave de acesso: 44 dígitos + DV mod11."""
    digits = only_digits(value)
    if len(digits) != 44:
        return False
    body = digits[:43]
    weights = [4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(d) * w for d, w in zip(body, weights))
    dv = 11 - (total % 11)
    dv = 0 if dv >= 10 else dv
    return str(dv) == digits[43]


def _cnpj_checksum(body: str) -> str:
    def dv(seq: str, weights: list[int]) -> str:
        total = sum(int(d) * w for d, w in zip(seq, weights))
        rem = total % 11
        return "0" if rem < 2 else str(11 - rem)

    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = dv(body, w1)
    d2 = dv(body + d1, w2)
    return d1 + d2


def _cpf_checksum(body: str) -> str:
    def dv(seq: str) -> str:
        total = sum(int(d) * (len(seq) + 1 - i) for i, d in enumerate(seq))
        rem = (total * 10) % 11
        return "0" if rem == 10 else str(rem)

    d1 = dv(body)
    d2 = dv(body + d1)
    return d1 + d2
