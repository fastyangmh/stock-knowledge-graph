"""Fail-closed Linux scheduler entrypoint. No automatic publishing without opt-in."""
import argparse
import subprocess
import sys
from datetime import datetime,time
from pathlib import Path
from zoneinfo import ZoneInfo
from .core import ROOT
from .trading_calendar import is_trading_day

TZ=ZoneInfo("Asia/Taipei")

def ready(calendar,date,clock,cutoff=time(18,30)):
    if clock<cutoff:raise RuntimeError("Not yet past the configured after-close cutoff")
    return is_trading_day(calendar,date)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--calendar",type=Path,required=True)
    p.add_argument("--input",type=Path,required=True,help="Normalized private JSON from licensed sources")
    p.add_argument("--publish",action="store_true",help="Explicitly opt into Git push")
    p.add_argument("--universe",type=Path,required=True,help="Date-effective TW50 CSV")
    p.add_argument("--db",type=Path,default=ROOT/"local"/"stock_graph.db")
    p.add_argument("--preview-output",type=Path,default=ROOT/"local"/"private"/"preview")
    p.add_argument("--cutoff",default="18:30")
    args=p.parse_args()
    current=datetime.now(TZ)
    hh,mm=map(int,args.cutoff.split(":"))
    if not ready(args.calendar,current.date().isoformat(),current.time(),time(hh,mm)):
        print("Market closed: skip")
        return
    if not args.input.is_file():
        raise FileNotFoundError("Normalized input not found; refuse sample fallback")
    def run(*cmd):
        subprocess.run([sys.executable,"-m",*cmd],cwd=ROOT,check=True)
    if args.publish:
        raise RuntimeError("Automatic publication is not enabled: first validate the private preview, then use local.publish manually")
    if args.preview_output.resolve()==(ROOT/"data").resolve() or args.preview_output.resolve().is_relative_to((ROOT/"data").resolve()):
        raise ValueError("Preview output must not be the public data directory")
    run("local.pipeline","all","--semantic","--input",str(args.input),
        "--db",str(args.db),"--output",str(args.preview_output),
        "--universe",str(args.universe),"--as-of",current.date().isoformat(),
        "--lifecycle","--threshold","0.65")
    print("Private preview exported and validated by the exporter:",args.preview_output)
    else:
        print("Validated locally; no push (use --publish to opt in)")

if __name__=="__main__":
    main()
