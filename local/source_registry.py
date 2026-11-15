"""Dataset-level permission gate. No dataset is enabled by default.

Only register official machine-readable resources after checking dataset-specific
license and attribution. Generic TWSE/MOPS web pages are NOT approved sources.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_HOSTS={"openapi.twse.com.tw","www.tpex.org.tw","data.gov.tw"}

def load_approved(registry):
    records=json.loads(Path(registry).read_text(encoding="utf-8"))
    if not isinstance(records,list):
        raise ValueError("registry must be a JSON list")
    approved=[]
    seen=set()
    for item in records:
        ident=item["dataset_id"]
        if not isinstance(ident,str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}",ident):
            raise ValueError("unsafe dataset id")
        if ident in seen:raise ValueError("duplicate dataset id")
        seen.add(ident)
        if not item.get("enabled",False):
            continue
        if item.get("license_reviewed") is not True or not item.get("redistribution_reviewed") is True:
            raise ValueError(f"{ident}: licensing review incomplete")
        if not all(item.get(k) for k in ("provider","dataset_url","resource_url","license_url","attribution")):
            raise ValueError(f"{ident}: missing source attribution or license metadata")
        url=urlparse(item["resource_url"])
        if url.scheme!="https" or url.hostname not in ALLOWED_HOSTS or url.username or url.password:
            raise ValueError(f"{ident}: resource URL host is not approved")
        approved.append(item)
    return approved
