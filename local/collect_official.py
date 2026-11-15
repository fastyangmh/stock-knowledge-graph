"""Conservative downloader for explicitly approved government open datasets.

Downloads are stored in ignored local/private; never automatically published.
"""
import argparse
import json
import time
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from .source_registry import load_approved,ALLOWED_HOSTS
from urllib.parse import urlparse
from .core import ROOT,now

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None

def download(registry,output_dir,timeout=20,max_bytes=15_000_000):
    datasets=load_approved(registry)
    out=Path(output_dir).resolve()
    if out.is_relative_to((ROOT/"data").resolve()):
        raise ValueError("Cannot download raw official datasets into public data/")
    out.mkdir(parents=True,exist_ok=True)
    opener=build_opener(NoRedirect())
    results=[]
    for item in datasets:
        url=item["resource_url"]
        request=Request(url,headers={"User-Agent":"StockKnowledgeGraph/0.1 (licensed open data research)"})
        with opener.open(request,timeout=timeout) as response:
            content_length=response.headers.get("Content-Length")
            if content_length and int(content_length)>max_bytes:
                raise ValueError("dataset exceeds size limit")
            body=response.read(max_bytes+1)
            if len(body)>max_bytes:
                raise ValueError("dataset exceeds size limit")
        # Opaque source snapshot: do not assume provider-specific schema.
        path=out/(item["dataset_id"]+".json")
        path.write_bytes(body)
        results.append({"dataset_id":item["dataset_id"],"bytes":len(body),"retrieved_at":now(),
                        "resource_url":url,"attribution":item["attribution"]})
        time.sleep(1.0)
    (out/"retrieval_manifest.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    return results

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--registry",type=Path,default=ROOT/"local"/"official_datasets.json")
    p.add_argument("--output-dir",type=Path,default=ROOT/"local"/"private"/"official")
    args=p.parse_args()
    print("Downloaded",len(download(args.registry,args.output_dir)),"approved datasets")

if __name__=="__main__":
    main()
