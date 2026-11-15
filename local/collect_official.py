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
from .official_adapter import csv_rows


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
    opener = build_opener(NoRedirect())
    for attempt in range(3):
        try:
            request = Request(url,headers={"User-Agent":"StockKnowledgeGraph/0.2 (official open-data local research)",
                                          "Accept":"text/csv"})
            with opener.open(request,timeout=timeout) as response:
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > max_bytes:
                    raise ValueError("Dataset exceeds size limit")
                body = response.read(max_bytes+1)
                if len(body)>max_bytes:
                    raise ValueError("Dataset exceeds size limit")
            csv_rows(body)  # Reject HTML error pages and malformed/empty CSV before persistence.
            return body
        except HTTPError as exc:
            if exc.code not in (429,500,502,503,504) or attempt == 2:
                raise
            retry = (exc.headers or {}).get("Retry-After", "")
            delay = min(float(retry),30) if retry.isdigit() else 2**attempt
            time.sleep(max(1,delay))
    raise AssertionError("unreachable")


def download(registry, output_dir, timeout=20, max_bytes=15_000_000):
    datasets = load_approved(registry)
    if not datasets:
        raise ValueError("No reviewed enabled datasets; refusing an empty successful collection")
    out = private_path(output_dir)
    out.mkdir(parents=True,exist_ok=True)
    results = []
    with exclusive_lock(out):
        for index,item in enumerate(datasets):
            if item.get("format") != "csv":
                raise ValueError("Only reviewed CSV feeds are supported")
            if index:
                time.sleep(1)
            body = fetch_csv(item["resource_url"],timeout,max_bytes)
            checksum = hashlib.sha256(body).hexdigest()
            relative = f"{item['dataset_id']}/{checksum}.csv"
            path = out/relative
            if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
                raise ValueError("An immutable snapshot has been modified")
            if not path.exists():
                atomic_bytes(path,body)
            results.append({"dataset_id":item["dataset_id"],"path":relative,"sha256":checksum,
                "bytes":len(body),"retrieved_at":now(),"resource_url":item["resource_url"],
                "attribution":item["attribution"],"license_url":item["license_url"]})
        manifest = {"schema_version":"1.0","generated_at":now(),"datasets":results}
        encoded = (json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode()
        atomic_bytes(out/("retrieval-"+uuid.uuid4().hex+".json"),encoded)
        atomic_bytes(out/"retrieval_manifest.json",encoded)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry",type=Path,default=ROOT/"local"/"official_datasets.json")
    parser.add_argument("--output-dir",type=Path,default=ROOT/"local"/"private"/"official")
    args = parser.parse_args()
    print("Downloaded",len(download(args.registry,args.output_dir)),"reviewed datasets to private snapshots")


if __name__ == "__main__":
    main()
