"""Adapters for the reviewed MOPS open-data company/revenue CSV datasets.

Do not scrape MOPS web forms. Monetary values retain the source's numeric
scale (unit=source_reported) rather than guessing a currency multiplier.
Availability is first observed at retrieval, never the revenue period end.
"""
from __future__ import annotations
import calendar
import csv
import hashlib
import io
import json
import math
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo
from .dates import iso_date, timestamp
from .source_registry import load_approved


def csv_rows(body: bytes) -> list[dict[str, str]]:
    text = body.decode("utf-8-sig")
    if text.lstrip().startswith("<"):
        raise ValueError("Expected CSV, received HTML/XML")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    headers = [field.strip() for field in (reader.fieldnames or [])]
    if not headers or any(not field for field in headers) or len(headers) != len(set(headers)):
        raise ValueError("Missing or duplicated CSV headers")
    reader.fieldnames = headers
    rows = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("CSV row length does not match header")
        if any(value.strip() for value in row.values()):
            rows.append({key.strip():value.strip() for key,value in row.items()})
    if not rows:
        raise ValueError("Empty official dataset")
    return rows


def report_date(value: str) -> date:
    if re.fullmatch(r"\d{7}",value):
        return date(int(value[:3])+1911,int(value[3:5]),int(value[5:]))
    if re.fullmatch(r"\d{8}",value):
        return date(int(value[:4]),int(value[4:6]),int(value[6:]))
    return iso_date(value)


def month_end(value: str) -> str:
    if re.fullmatch(r"\d{5}",value):
        year,month = int(value[:3])+1911,int(value[3:])
    elif re.fullmatch(r"\d{6}",value):
        year,month = int(value[:4]),int(value[4:])
    else:
        raise ValueError("資料年月 must be ROC YYYMM or Gregorian YYYYMM")
    return date(year,month,calendar.monthrange(year,month)[1]).isoformat()


def number(value: str):
    if value.strip() in ("", "--", "-", "N/A"):
        return None
    original = value.strip()
    if "," in original and not re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d*)?", original):
        raise ValueError("Invalid thousands separator grouping")
    cleaned = original.replace(",", "")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)",cleaned):
        raise ValueError("Invalid financial number")
    try:
        decimal = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError("Invalid financial number") from exc
    if not decimal.is_finite() or not math.isfinite(float(decimal)):
        raise ValueError("Non-finite financial value")
    # Preserve integers exactly in the normalized JSON; raw snapshots remain authoritative.
    return int(decimal) if decimal == decimal.to_integral_value() else float(decimal)


def normalize_records(datasets, universe, *, as_of):
    """datasets = [(reviewed_registry_entry, rows, retrieved_at), ...]. No IO."""
    selected = set(universe)
    if not selected:
        raise ValueError("Empty universe")
    target = iso_date(as_of)
    stocks, documents, metrics, sources = {}, {}, {}, {}
    observed_times = []
    company_ids, revenue_ids = set(), set()
    seen_datasets = set()
    for source,rows,retrieved_at in datasets:
        sid = source["dataset_id"]
        if sid in seen_datasets:
            raise ValueError("Duplicate dataset snapshot")
        seen_datasets.add(sid)
        observed = timestamp(retrieved_at)
        observed_day = observed.astimezone(ZoneInfo("Asia/Taipei")).date()
        if observed_day != target:
            raise ValueError("Snapshot retrieval day does not match universe/as-of day; no retrospective backfill")
        observed_times.append(observed.isoformat())
        sources[sid] = {"source_id":sid,"provider":source["provider"],
                        "url":source["dataset_url"],"license_type":"OGDL-1.0"}
        required = {"出表日期","公司代號","公司名稱"}
        if source["kind"] == "monthly_revenue":
            required |= {"資料年月","營業收入-當月營收"}
        elif source["kind"] != "companies":
            raise ValueError("Unsupported official dataset kind")
        if not rows or any(not required.issubset(row) for row in rows):
            raise ValueError(f"{sid}: required source fields are missing")
        seen_rows = set()
        for row in rows:
            code = row["公司代號"].strip()
            if not re.fullmatch(r"\d{4}",code):
                # Non-common-stock instrument codes are outside this TW50 adapter.
                continue
            stock_id = "TW:"+code
            if stock_id not in selected:
                continue
            reported = report_date(row["出表日期"])
            if reported > observed_day:
                raise ValueError("Source report date is in the future")
            if not row["公司名稱"].strip():
                raise ValueError("Empty company name")
            provenance = {"source_id":sid,"source_url":source["dataset_url"],
                          "license_url":source["license_url"],"attribution":source["attribution"]}
            if source["kind"] == "companies":
                if stock_id in stocks:
                    raise ValueError("Duplicate company record for selected stock")
                company_ids.add(stock_id)
                stocks[stock_id] = {"stock_id":stock_id,"ticker":code,"market":"TW",
                    "name":row.get("公司簡稱") or row["公司名稱"],"industry":row.get("產業別"),**provenance}
                continue
            period = month_end(row["資料年月"])
            if iso_date(period) > reported:
                raise ValueError("Revenue period is later than report date")
            row_key = (stock_id,period)
            if row_key in seen_rows:
                raise ValueError("Duplicate revenue period; explicit revision selection required")
            seen_rows.add(row_key)
            value = number(row["營業收入-當月營收"])
            if value is None:
                continue  # Missing is not zero; coverage below will fail for a missing selected issuer.
            revenue_ids.add(stock_id)
            doc_id = f"{sid}:{code}:{period[:7]}"
            if doc_id in documents:
                raise ValueError("Conflicting revenue document")
            records = [("monthly_revenue",value,"source_reported")]
            for field,metric in (("營業收入-上月比較增減(%)","monthly_revenue_mom_pct"),
                                 ("營業收入-去年同月增減(%)","monthly_revenue_yoy_pct")):
                parsed = number(row.get(field,""))
                if parsed is not None:
                    records.append((metric,parsed,"percent"))
            for metric,val,unit in records:
                key = (stock_id,metric,period)
                if key in metrics:
                    raise ValueError("Conflicting metric source")
                metrics[key] = {"stock_id":stock_id,"metric":metric,"period_end":period,"period_type":"month",
                    "value":val,"unit":unit,"available_at":observed.isoformat(),"source_id":sid}
            text = f"{row['公司名稱']} {period[:7]} 月營收：{value}（來源原始數值，未換算幣別與倍率）。"
            documents[doc_id] = {"document_id":doc_id,"external_id":doc_id,"doc_type":"financial",
                "title":f"{code} {period[:7]} 月營收","content":text,"stock_ids":[stock_id],
                "published_at":observed.isoformat(),"available_at":observed.isoformat(),
                "availability_basis":"observed_at_retrieval_not_original_publication",
                "source_report_date":reported.isoformat(),"period_end":period,"unit":"source_reported",**provenance}
    missing = selected-company_ids
    if missing:
        raise ValueError("Company coverage incomplete: "+", ".join(sorted(missing)))
    missing = selected-revenue_ids
    if missing:
        raise ValueError("Revenue coverage incomplete: "+", ".join(sorted(missing)))
    return {"stocks":[stocks[k] for k in sorted(stocks)],"sources":[sources[k] for k in sorted(sources)],
            "documents":[documents[k] for k in sorted(documents)],"financial_metrics":[metrics[k] for k in sorted(metrics)],
            "chip_metrics":[],"metadata":{"adapter_version":"official-csv-v1","universe_as_of":as_of,
                "observed_at":max(observed_times),"company_coverage":len(company_ids),"revenue_coverage":len(revenue_ids),
                "unit_policy":"Monetary values retain source numeric scale; not safe for cross-source monetary comparisons."}}


def from_snapshots(directory, registry, universe, *, as_of):
    root = Path(directory).resolve()
    sources = {s["dataset_id"]:s for s in load_approved(registry)}
    manifest = json.loads((root/"retrieval_manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest,dict) or manifest.get("schema_version") != "1.0":
        raise ValueError("Collect new versioned snapshots first")
    datasets = []
    for entry in manifest["datasets"]:
        source = sources.get(entry["dataset_id"])
        if not source or source["resource_url"] != entry["resource_url"]:
            raise ValueError("Snapshot source is not in reviewed registry")
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe snapshot path")
        path = root/relative
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Snapshot path escapes private directory")
        body = path.read_bytes()
        if len(body) != entry["bytes"] or hashlib.sha256(body).hexdigest() != entry["sha256"]:
            raise ValueError("Snapshot checksum/length mismatch")
        datasets.append((source,csv_rows(body),entry["retrieved_at"]))
    payload = normalize_records(datasets,universe,as_of=as_of)
    payload["metadata"]["source_snapshots"] = [
        {k: entry[k] for k in ("dataset_id", "sha256", "bytes", "retrieved_at", "resource_url")}
        for entry in manifest["datasets"]]
    return payload
