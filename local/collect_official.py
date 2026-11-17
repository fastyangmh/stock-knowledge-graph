"""Fetch reviewed open-data CSVs only, into immutable private snapshots.

No MOPS form scraping, authentication bypass, index-constituent scraping,
public exports, Git operations or scheduling. A failed batch keeps its prior
retrieval manifest; successful snapshots are SHA256-addressed and reusable.
"""
import argparse
import hashlib
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from .core import ROOT, now
from .source_registry import load_approved
from .safety import exclusive_lock, private_path
from zoneinfo import ZoneInfo
from .dates import timestamp
from .research_history import validate_symbols
from .official_adapter import csv_rows, dataset_profile, normalize_records
from .http_evidence import body_metadata, capture_response


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


def atomic_bytes(path, body):
    path.parent.mkdir(parents=True,exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as out:
            name = out.name
            out.write(body)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name,path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def fetch_csv(url, timeout=20, max_bytes=15_000_000):
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    opener = build_opener(NoRedirect())
    for attempt in range(3):
        try:
            request = Request(url,headers={"User-Agent":"StockKnowledgeGraph/0.2 (official open-data local research)",
                                          "Accept":"text/csv"})
            with opener.open(request,timeout=timeout) as response:
                body = capture_response(response, url, max_bytes)
            try:
                csv_rows(body)  # Reject HTML/error pages before successful persistence.
            except (ValueError, UnicodeError) as exc:
                exc.response_body = body
                exc.error_category = "csv_validation"
                raise
            return body
        except HTTPError as exc:
            if exc.code not in (429,500,502,503,504) or attempt == 2:
                try:
                    captured = capture_response(exc, url, max_bytes)
                except ValueError as size_error:
                    captured = size_error.response_body
                exc.response_body = captured
                raise
            retry = (exc.headers or {}).get("Retry-After", "")
            delay = min(float(retry),30) if retry.isdigit() else 2**attempt
            time.sleep(max(1,delay))
    raise AssertionError("unreachable")


def save_failure(out, item, completed, stage, exc, body=None):
    attempt_id = uuid.uuid4().hex
    captured = getattr(exc, "response_body", body)
    failure = {"dataset_id": item["dataset_id"], "resource_url": item["resource_url"],
               "retrieved_at": now(), "stage": stage, "error_type": type(exc).__name__,
               "error": str(exc), "error_category": getattr(exc, "error_category", (
                   "http_error" if isinstance(exc, HTTPError) else
                   "network_error" if isinstance(exc, OSError) else "validation_error")),
               **body_metadata(captured, item["resource_url"])}
    if hasattr(exc, "profile"):
        failure["profile"] = exc.profile
    if captured is not None:
        relative = f"failures/{attempt_id}.bin"
        atomic_bytes(out / relative, captured)
        truncated = failure.get("body_truncated", False)
        checksum = hashlib.sha256(captured).hexdigest()
        failure.update(path=relative, bytes=len(captured), body_truncated=truncated,
                       captured_sha256=checksum, sha256=None if truncated else checksum)
    else:
        failure.update(path=None, bytes=None, body_truncated=None, sha256=None)
    report = {"schema_version": "1.0", "status": "failed", "generated_at": now(),
              "datasets": completed, "failure": failure}
    atomic_bytes(out / f"retrieval-failure-{attempt_id}.json",
                 (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode())


def download(registry, output_dir, timeout=20, max_bytes=15_000_000, *, symbols=None):
    selected = validate_symbols(symbols) if symbols is not None else set()
    datasets = load_approved(registry)
    if not datasets:
        raise ValueError("No reviewed enabled datasets; refusing an empty successful collection")
    out = private_path(output_dir)
    out.mkdir(parents=True,exist_ok=True)
    results = []
    normalized_inputs = []
    with exclusive_lock(out):
        for index,item in enumerate(datasets):
            stage = "fetch"
            body = None
            try:
                if item.get("format") != "csv":
                    raise ValueError("Only reviewed CSV feeds are supported")
                if index:
                    time.sleep(1)
                body = fetch_csv(item["resource_url"],timeout,max_bytes)
                retrieved_at = now()
                stage = "full_file_profile"
                rows = csv_rows(body)
                profile = dataset_profile(item, rows, retrieved_at, selected)
                normalized_inputs.append((item, rows, retrieved_at))
                stage = "snapshot_persistence"
                checksum = hashlib.sha256(body).hexdigest()
                relative = f"{item['dataset_id']}/{checksum}.csv"
                path = out/relative
                if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
                    raise ValueError("An immutable snapshot has been modified")
                if not path.exists():
                    atomic_bytes(path,body)
                results.append({"dataset_id":item["dataset_id"],"path":relative,"sha256":checksum,
                    "bytes":len(body),"retrieved_at":retrieved_at,"profile":profile,"resource_url":item["resource_url"],
                    "attribution":item["attribution"],"license_url":item["license_url"],
                    **body_metadata(body, item["resource_url"])})
            except Exception as exc:
                save_failure(out, item, results, stage, exc, body)
                raise
        if selected:
            try:
                as_of = timestamp(normalized_inputs[-1][2]).astimezone(ZoneInfo("Asia/Taipei")).date().isoformat()
                normalize_records(normalized_inputs, selected, as_of=as_of)
            except Exception as exc:
                save_failure(out, item, results, "selected_values", exc, body)
                raise
        manifest = {"schema_version":"1.0","generated_at":now(),"datasets":results,
                    "selected_value_validation": "passed" if selected else "not_requested"}
        encoded = (json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode()
        atomic_bytes(out/("retrieval-"+uuid.uuid4().hex+".json"),encoded)
        atomic_bytes(out/"retrieval_manifest.json",encoded)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry",type=Path,default=ROOT/"local"/"official_datasets.json")
    parser.add_argument("--output-dir",type=Path,default=ROOT/"local"/"private"/"official")
    parser.add_argument("--symbols", nargs="+", help="Explicit codes to validate before advancing the batch")
    parser.add_argument("--max-bytes", type=int, default=15_000_000)
    parser.add_argument("--timeout", type=float, default=20)
    args = parser.parse_args(argv)
    print("Downloaded",len(download(args.registry,args.output_dir,args.timeout,args.max_bytes,symbols=args.symbols)),"reviewed datasets to private snapshots")


if __name__ == "__main__":
    main()
