from dataclasses import dataclass
from datetime import date
from typing import Optional

ACCESS_LEVELS = ["public", "customer", "agent", "admin"]

@dataclass
class DocMetadata:
    doc_id: str
    title: str
    doc_type: str            # faq | policy | guide | product_doc
    version: str
    product: str
    region: str
    access_level: str
    effective_date: date
    expiry_date: Optional[date]
    content_hash: str
    source_path: str

def validate(m: DocMetadata):
    if m.access_level not in ACCESS_LEVELS:
        raise ValueError("invalid access_level")
    if m.expiry_date and m.expiry_date <= m.effective_date:
        raise ValueError("expiry must be after effective date")