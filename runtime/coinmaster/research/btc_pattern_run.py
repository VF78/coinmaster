"""Single staged CLI; fit/evaluation require exact coordinator receipts."""
import argparse,json,os
from pathlib import Path
from .btc_pattern_data import prepare

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','smoke','train','evaluate','policy','sol','forward-dry-run'])
    p.add_argument('--protocol',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--old-prepared',type=Path);p.add_argument('--prepared',type=Path);p.add_argument('--authorization',type=Path);p.add_argument('--input',type=Path)
    a=p.parse_args()
    if a.stage=='prepare':print(json.dumps(prepare(a)));return
    if a.stage=='smoke':
        from .btc_pattern_smoke import smoke
        print(json.dumps(smoke(a)));return
    if a.stage=='train':
        from .btc_pattern_train import train
        print(json.dumps(train(a)));return
    if a.stage=='evaluate':
        from .btc_pattern_evaluate import evaluate
        print(json.dumps(evaluate(a)));return
    raise SystemExit('BLOCKED_STAGE_NOT_YET_ADMITTED: exact protocol/source/resource GO and implementation required')
if __name__=='__main__':main()
