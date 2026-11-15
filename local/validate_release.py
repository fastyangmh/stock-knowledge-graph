"""Validate all public JSON before publication. Python stdlib only."""
import argparse
import json
from pathlib import Path
from .export_json import validate_graph

def validate_release(root):
    root=Path(root).resolve()
    data=root/"data"
    manifest=json.loads((data/"manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest.get("stocks"),list) or not manifest["stocks"]:
        raise ValueError("manifest requires nonempty stocks list")
    paths=set()
    for stock in manifest["stocks"]:
        relative=stock["path"]
        if not isinstance(relative,str) or not relative.startswith("data/") or not relative.endswith("/graph.json"):
            raise ValueError("invalid manifest path")
        path=(root/relative).resolve()
        if not path.is_relative_to(data.resolve()):
            raise ValueError("manifest path escapes data directory")
        if path in paths:
            raise ValueError("duplicate manifest path")
        paths.add(path)
        graph=json.loads(path.read_text(encoding="utf-8"))
        if not graph.get("stock_id"):
            raise ValueError("graph missing stock_id")
        validate_graph(graph)
    # Require manifest to describe every exported graph, preventing stale public files.
    found=set(data.glob("stocks/**/graph.json"))
    if {p.resolve() for p in found} != paths:
        raise ValueError("unlisted or missing stock graph files")
    return len(paths)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    args=p.parse_args()
    print("Validated",validate_release(args.root),"published stock graphs")

if __name__=="__main__":
    main()
