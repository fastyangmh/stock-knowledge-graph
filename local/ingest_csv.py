"""Normalize licensed/local CSV exports into pipeline input JSON.

No external API calls; only user-provided local files. All timestamps must be
ISO-8601 with timezone offsets. Intended for first real-data integration.
"""
import argparse
import csv
import json
import math
from pathlib import Path
from .core import digest

KINDS={
 "stocks":("stock_id","ticker","market","name"),
 "documents":("document_id","doc_type","title","published_at"),
 "sources":("source_id","provider"),
 "financial_metrics":("stock_id","metric","period_end","period_type","value","available_at"),
 "chip_metrics":("stock_id","trade_date","metric","value")
}
def read_csv(path,kind):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        missing=set(KINDS[kind])-set(reader.fieldnames or [])
        if missing:raise ValueError(f"{kind}: missing columns {sorted(missing)}")
        rows=[]
        for index,row in enumerate(reader,2):
            if not any((v or "").strip() for v in row.values()):continue
            for key in KINDS[kind]:
                if not (row.get(key) or "").strip():
                    raise ValueError(f"{kind}:{index}: empty {key}")
            clean={k:v.strip() for k,v in row.items() if k and v is not None and v.strip()}
            if kind=="documents":
                clean["stock_ids"]=[x.strip() for x in clean.pop("stock_ids","").split(";") if x.strip()]
            if kind in ("financial_metrics","chip_metrics"):
                try:clean["value"]=float(clean["value"])
                except ValueError as exc:raise ValueError(f"{kind}:{index}: invalid value") from exc
            if kind in ("financial_metrics","chip_metrics") and not math.isfinite(clean["value"]):
                raise ValueError(f"{kind}:{index}: non-finite value")
            rows.append(clean)
        return rows

def normalize(folder):
    folder=Path(folder)
    payload={}
    for kind in KINDS:
        path=folder/(kind+".csv")
        payload[kind]=read_csv(path,kind) if path.exists() else []
    if not payload["stocks"]:
        raise ValueError("stocks.csv must exist and contain at least one stock")
    known={s["stock_id"] for s in payload["stocks"]}
    for doc in payload["documents"]:
        unknown=set(doc["stock_ids"])-known
        if unknown:raise ValueError(f"document {doc['document_id']} references missing stocks: {sorted(unknown)}")
    for kind in ("financial_metrics","chip_metrics"):
        for row in payload[kind]:
            if row["stock_id"] not in known:
                raise ValueError(f"{kind} references missing stock {row['stock_id']}")
    return payload

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]/"data"):
        raise ValueError("Normalized private input must not be written to public data/")
    payload=normalize(args.input_dir)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Normalized",len(payload["stocks"]),"stocks and",len(payload["documents"]),"documents")

if __name__=="__main__":
    main()
