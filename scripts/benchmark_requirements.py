#!/usr/bin/env python3
"""Measure deterministic requirement extraction against the versioned fixture set."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]; API_ROOT=ROOT/"apps"/"api"
if str(API_ROOT) not in sys.path: sys.path.insert(0,str(API_ROOT))
from app.domains.requirements.extractor import DeterministicRequirementExtractor  # noqa: E402
FIXTURE_PATH=API_ROOT/"tests"/"fixtures"/"requirements_accuracy_cases.json"
def norm(parameter:str,value:Any):
    return parameter,float(value) if isinstance(value,(int,float)) and not isinstance(value,bool) else value
def evaluate_cases(cases:list[dict[str,Any]])->dict[str,Any]:
    extractor=DeterministicRequirementExtractor();tp=fp=fn=0;results=[]
    for case in cases:
        expected={norm(p,v) for p,v in case["expected"]};actual={norm(c.parameter,c.normalized_value) for c in extractor.extract(case["brief"])}
        a,b,c=len(expected&actual),len(actual-expected),len(expected-actual);tp+=a;fp+=b;fn+=c
        results.append({"id":case["id"],"passed":expected==actual,"true_positive":a,"false_positive":b,"false_negative":c,
            "missing":sorted([list(x) for x in expected-actual],key=str),"unexpected":sorted([list(x) for x in actual-expected],key=str)})
    precision=tp/(tp+fp) if tp+fp else 1.;recall=tp/(tp+fn) if tp+fn else 1.;f1=2*precision*recall/(precision+recall) if precision+recall else 0.
    return {"fixture_count":len(cases),"passed_cases":sum(r["passed"] for r in results),"true_positive":tp,"false_positive":fp,"false_negative":fn,
        "precision":round(precision,4),"recall":round(recall,4),"f1":round(f1,4),"cases":results}
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--min-f1",type=float,default=.95);parser.add_argument("--min-precision",type=float,default=.95);parser.add_argument("--min-recall",type=float,default=.95);args=parser.parse_args()
    try: cases=json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc: print(f"FAIL: unable to load benchmark fixtures: {exc}",file=sys.stderr);return 2
    report=evaluate_cases(cases);print(json.dumps(report,indent=2,sort_keys=True))
    if report["f1"]<args.min_f1 or report["precision"]<args.min_precision or report["recall"]<args.min_recall or report["passed_cases"]!=report["fixture_count"]:
        print(f"FAIL: benchmark thresholds not met (precision >= {args.min_precision}, recall >= {args.min_recall}, F1 >= {args.min_f1})",file=sys.stderr);return 1
    print("PASS: requirement extraction benchmark meets precision, recall, F1, and exact-match gates.");return 0
if __name__=="__main__": raise SystemExit(main())
