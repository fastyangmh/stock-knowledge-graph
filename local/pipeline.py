"""CLI: python -m local.pipeline init|import|similarity|export|all|validate"""
import argparse
import json
import sys
from pathlib import Path
from .core import DEFAULT_DB, ROOT, connect, init_db, import_payload, now
from .similarity import compute
from .export_json import export, validate_graph

def main(argv=None):
    parser=argparse.ArgumentParser(description="Local stock knowledge graph pipeline")
    parser.add_argument("command",choices=["init","import","similarity","export","all","validate"])
    parser.add_argument("--db",type=Path,default=DEFAULT_DB)
    parser.add_argument("--input",type=Path,default=ROOT/"local"/"sample_data.json")
    parser.add_argument("--output",type=Path,default=ROOT/"data")
    parser.add_argument("--top-k",type=int,default=10)
    parser.add_argument("--threshold",type=float,default=0.15)
    args=parser.parse_args(argv)
    if args.command=="validate":
        manifest=json.loads((args.output/"manifest.json").read_text(encoding="utf-8"))
        for stock in manifest["stocks"]:
            path=ROOT/stock["path"] if args.output==ROOT/"data" else args.output/stock["path"].removeprefix("data/")
            validate_graph(json.loads(path.read_text(encoding="utf-8")))
        print("Validated",len(manifest["stocks"]),"stock graphs")
        return
    with connect(args.db) as conn:
        init_db(conn)
        run=conn.execute("INSERT INTO pipeline_runs(started_at,status) VALUES(?,?)",(now(),"running")).lastrowid
        conn.commit()
        try:
            if args.command in ("import","all"):
                import_payload(conn,json.loads(args.input.read_text(encoding="utf-8")))
            if args.command in ("similarity","all"):
                print("Similarity:",compute(conn,args.top_k,args.threshold))
            if args.command in ("export","all"):
                print("Exported",len(export(conn,args.output)["stocks"]),"stocks")
            conn.execute("UPDATE pipeline_runs SET finished_at=?,status=? WHERE run_id=?",(now(),"success",run))
            conn.commit()
        except Exception as e:
            conn.rollback()
            conn.execute("UPDATE pipeline_runs SET finished_at=?,status=?,details=? WHERE run_id=?",(now(),"failed",str(e),run))
            conn.commit()
            raise

if __name__=="__main__":
    main()
