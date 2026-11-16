"""CLI: python -m local.pipeline init|import|similarity|export|all|validate"""
import argparse
import json
import sys
from pathlib import Path
from .core import DEFAULT_DB, ROOT, connect, init_db, import_payload, now
from .similarity import compute
from .semantic import compute_semantic, DEFAULT_MODEL
from .export_json import export, validate_graph
from .universe import load_universe
from .combined_universe import load_combined_universe

def main(argv=None):
    parser=argparse.ArgumentParser(description="Local stock knowledge graph pipeline")
    parser.add_argument("command",choices=["init","import","similarity","semantic","export","all","validate"])
    parser.add_argument("--db",type=Path,default=DEFAULT_DB)
    parser.add_argument("--input",type=Path,default=ROOT/"local"/"sample_data.json")
    parser.add_argument("--output",type=Path,default=ROOT/"data")
    parser.add_argument("--top-k",type=int,default=10)
    parser.add_argument("--threshold",type=float,default=None)
    parser.add_argument("--model",default=DEFAULT_MODEL,help="Sentence Transformers model ID")
    parser.add_argument("--revision",default=None,help="Pin model revision / commit SHA for reproducibility")
    parser.add_argument("--batch-size",type=int,default=32)
    parser.add_argument("--universe",type=Path,help="Point-in-time TW50 membership CSV")
    parser.add_argument("--etf-holdings",type=Path,help="Optional same-day 009816 holdings; union with --universe")
    parser.add_argument("--universe-source",help="HTTPS provenance URL of TW50 membership file")
    parser.add_argument("--as-of",help="Membership date YYYY-MM-DD (defaults to today)")
    parser.add_argument("--lifecycle",action="store_true",help="Prune published graph without deleting SQLite history")
    parser.add_argument("--semantic",action="store_true",help="Use sentence-transformers for all command")
    parser.add_argument("--lookback-days",type=int,default=None,help="Optional active semantic document window")
    parser.add_argument("--max-pairs",type=int,default=2_000_000,help="Fail before an excessive exact pair scan")
    args=parser.parse_args(argv)
    if args.command=="validate":
        from .validate_release import validate_data_dir
        count=validate_data_dir(args.output)
        print("Validated",count,"stock graphs")
        return
    if args.etf_holdings and not (args.universe and args.as_of and args.universe_source):
        parser.error("--etf-holdings requires --universe, --as-of and --universe-source")
    if args.etf_holdings and args.command not in ("import","all","export"):
        parser.error("--etf-holdings is supported for import, all and export")
    combined = (load_combined_universe(args.universe,args.etf_holdings,args.as_of,args.universe_source)
                if args.etf_holdings else None)
    with connect(args.db) as conn:
        init_db(conn)
        run=conn.execute("INSERT INTO pipeline_runs(started_at,status) VALUES(?,?)",(now(),"running")).lastrowid
        conn.commit()
        try:
            if args.command in ("import","all"):
                payload=json.loads(args.input.read_text(encoding="utf-8"))
                import_payload(conn,combined.annotate_payload(payload) if combined else payload)
            if args.command in ("similarity","all","semantic"):
                if args.command=="semantic" or (args.command=="all" and args.semantic):
                    threshold = 0.65 if args.threshold is None else args.threshold
                    print("Semantic:",compute_semantic(conn,args.model,args.top_k,threshold,args.batch_size,revision=args.revision,lookback_days=args.lookback_days,max_pairs=args.max_pairs))
                else:
                    print("Similarity:",compute(conn,args.top_k,0.15 if args.threshold is None else args.threshold))
            if args.command in ("export","all"):
                universe=combined.stock_ids if combined else (load_universe(args.universe,args.as_of) if args.universe else None)
                if combined:
                    combined.annotate_nodes(conn)
                print("Exported",len(export(conn,args.output,universe=universe,lifecycle=args.lifecycle)["stocks"]),"stocks")
            conn.execute("UPDATE pipeline_runs SET finished_at=?,status=? WHERE run_id=?",(now(),"success",run))
            conn.commit()
        except Exception as e:
            conn.rollback()
            conn.execute("UPDATE pipeline_runs SET finished_at=?,status=?,details=? WHERE run_id=?",(now(),"failed",str(e),run))
            conn.commit()
            raise

if __name__=="__main__":
    main()
