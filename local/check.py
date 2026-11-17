"""Local CI: syntax, all tests, isolated SQLite->JSON smoke, full validation.

Invoke with: uv run --locked python -m local.check
No network requests, model downloads or public data writes. Git publication
tests use temporary local bare repositories only.
"""
import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from .core import ROOT, now
from .safety import private_path
from .collect_official import atomic_bytes


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path,default=ROOT/"local/private/check-report.json")
    parser.add_argument("--runner",choices=("pytest","unittest"),default="pytest")
    parser.add_argument("--frontend",action="store_true",help="Also require Node.js syntax and offline browser-logic tests")
    args=parser.parse_args(argv)
    report_path=private_path(args.report)
    report={"started_at":now(),"python":sys.version,"platform":platform.platform(),"checks":[],
            "scope":"Offline synthetic fixtures and isolated lexical CLI. No live model/API/browser/remote deployment verification.",
            "source_sha256":{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted((ROOT/"local").rglob("*.py")) if "private" not in p.parts}}
    probes=[]
    def probe(command):
        try:
            result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=10)
            entry={"command":command,"exit_code":result.returncode,"output":result.stdout+result.stderr}
        except (OSError,subprocess.TimeoutExpired) as exc:
            entry={"command":command,"exit_code":None,"output":str(exc)}
        probes.append(entry)
        return entry["output"].strip() if entry["exit_code"]==0 else None

    commit=probe(["git","rev-parse","HEAD"])
    status=probe(["git","status","--porcelain"])
    report.update(repository={"commit":commit,"dirty":bool(status) if status is not None else None},
                  runner=args.runner,frontend_requested=args.frontend,
                  lock_sha256=hashlib.sha256((ROOT/"uv.lock").read_bytes()).hexdigest(),
                  environment={"os":platform.system(),"architecture":platform.machine(),
                               "python_version":platform.python_version(),"python_executable":sys.executable,
                               "uv_version":probe(["uv","--version"]),
                               "node_version":probe(["node","--version"])},
                  environment_probes=probes)
    tests=["pytest","-q"] if args.runner=="pytest" else ["unittest","discover","-s","local/tests","-v"]
    failed=False
    with tempfile.TemporaryDirectory(prefix="stock-graph-check-") as directory:
        tmp=Path(directory)
        steps=[["compileall","-q","local"],tests,
               ["local.pipeline","all","--db",str(tmp/"test.db"),"--input",str(ROOT/"local/sample_data.json"),
                "--output",str(tmp/"preview"),"--lifecycle"],
               ["local.pipeline","validate","--output",str(tmp/"preview")]]
        for module_args in steps:
            result=subprocess.run([sys.executable,"-m",*module_args],cwd=ROOT,text=True,capture_output=True)
            text=result.stdout+result.stderr
            print(text,end="" if text.endswith("\n") else "\n")
            report["checks"].append({"command":[sys.executable,"-m",*module_args],"exit_code":result.returncode,"output":text})
            if result.returncode:
                failed=True
                break
    if args.frontend and not failed:
        node=shutil.which("node")
        commands=([[node,"--check",str(p)] for p in sorted((ROOT/"js").glob("*.js"))]
                  + [[node,"--test",*[str(p) for p in sorted((ROOT/"js/tests").glob("*.test.js"))]]]) if node else []
        if not node:
            report["checks"].append({"command":["node"],"exit_code":1,"output":"--frontend requires Node.js; no silent skip"})
            failed=True
        for command in commands:
            result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
            text=result.stdout+result.stderr
            print(text,end="" if text.endswith("\n") else "\n")
            report["checks"].append({"command":command,"exit_code":result.returncode,"output":text})
            if result.returncode:
                failed=True
                break
        report["frontend_sha256"]={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sorted((ROOT/"js").rglob("*.js"))}
    report["site_sha256"]={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                           for name in ("index.html","history.html","event-study.html","css/style.css")}
    report.update(finished_at=now(),passed=not failed)
    atomic_bytes(report_path,(json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode())
    print("Local test report:",report_path)
    return 1 if failed else 0


if __name__=="__main__":
    raise SystemExit(main())
