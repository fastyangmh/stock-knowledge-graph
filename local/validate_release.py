"""Validate all public JSON before publication. Python stdlib only."""
import argparse
import json
import hashlib
import re
from .view_metadata import FIELDS, membership_summary, universe_counts
from pathlib import Path, PurePosixPath
from .export_json import validate_graph

def validate_release(root):
    return validate_data_dir(Path(root)/"data")

def validate_data_dir(directory):
    original=Path(directory)
    if original.is_symlink():
        raise ValueError("Symlink output directory is not allowed")
    data=original.resolve()
    for item in data.rglob("*"):
        if item.is_symlink():
            raise ValueError("Symlink in release")
    manifest=json.loads((data/"manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest.get("stocks"),list) or not manifest["stocks"]:
        raise ValueError("manifest requires nonempty stocks list")
    paths=set()
    for stock in manifest["stocks"]:
        relative=stock["path"]
        if not isinstance(relative,str) or not relative.startswith("data/") or not relative.endswith("/graph.json"):
            raise ValueError("invalid manifest path")
        tail=relative.removeprefix("data/")
        parts=PurePosixPath(tail).parts
        if ".." in parts or "\\" in tail or tail.startswith("/"):
            raise ValueError("unsafe manifest path")
        path=(data/tail).resolve()
        if not path.is_relative_to(data.resolve()):
            raise ValueError("manifest path escapes data directory")
        if path in paths:
            raise ValueError("duplicate manifest path")
        paths.add(path)
        body=path.read_bytes()
        if "sha256" in stock:
            checksum=stock["sha256"]
            if not isinstance(checksum,str) or not re.fullmatch(r"[0-9a-f]{64}",checksum):
                raise ValueError("Invalid graph checksum")
            if hashlib.sha256(body).hexdigest()!=checksum:
                raise ValueError("Graph checksum mismatch; mixed or modified release")
        graph=json.loads(body.decode("utf-8"))
        if not graph.get("stock_id"):
            raise ValueError("graph missing stock_id")
        validate_graph(graph)
        if "stock_id" in stock and stock["stock_id"]!=graph["stock_id"]:
            raise ValueError("Manifest stock_id differs from graph")
        for key,items in (("node_count",graph["nodes"]),("edge_count",graph["edges"])):
            if key in stock and (type(stock[key]) is not int or stock[key]!=len(items)):
                raise ValueError("Manifest graph count mismatch")
        if any(key in stock for key in FIELDS):
            primary=next((n for n in graph["nodes"] if n["id"]=="stock:"+graph["stock_id"]),None)
            if primary is None:
                raise ValueError("Primary stock node missing for membership")
            summary=membership_summary(primary)
            if not summary or any(stock.get(k)!=summary[k] for k in FIELDS):
                raise ValueError("Manifest and graph membership differ")
    # Require manifest to describe every exported graph, preventing stale public files.
    found=set(data.glob("stocks/**/graph.json"))
    if {p.resolve() for p in found} != paths:
        raise ValueError("unlisted or missing stock graph files")
    if "research_universe" in manifest:
        summary=manifest["research_universe"]
        dates=sorted({s["universe_as_of"] for s in manifest["stocks"] if "universe_as_of" in s})
        if (not isinstance(summary,dict) or summary.get("counts")!=universe_counts(manifest["stocks"])
                or summary.get("as_of_dates")!=dates):
            raise ValueError("Manifest universe summary mismatch")
    return len(paths)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    args=p.parse_args()
    print("Validated",validate_release(args.root),"published stock graphs")

if __name__=="__main__":
    main()
