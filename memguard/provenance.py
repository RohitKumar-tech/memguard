"""Trust lattice and provenance labels."""
from enum import IntEnum


class Trust(IntEnum):
    UNTRUSTED = 0   # web pages, emails, documents fetched by tools
    VERIFIED = 1    # internal systems of record (CRM, ERP)
    USER = 2        # the authenticated user's own instruction


SOURCE_TRUST = {
    'user': Trust.USER,
    'crm': Trust.VERIFIED,
    'erp': Trust.VERIFIED,
    'fetch_doc': Trust.UNTRUSTED,
    'email': Trust.UNTRUSTED,
    'web': Trust.UNTRUSTED,
}


def source_trust(source: str) -> Trust:
    """Unknown sources default to untrusted (fail closed)."""
    return SOURCE_TRUST.get(source, Trust.UNTRUSTED)


def derive_trust(parent_trusts) -> Trust:
    """A derived memory is only as trustworthy as its least trusted input."""
    parent_trusts = list(parent_trusts)
    return Trust(min(parent_trusts)) if parent_trusts else Trust.UNTRUSTED
