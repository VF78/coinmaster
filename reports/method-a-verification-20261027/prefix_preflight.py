"""Actual stock-loader P0/P1 preparation only; never constructs an engine."""
from pathlib import Path
import argparse,json
import prefix_common as common


def main():
    p=argparse.ArgumentParser();p.add_argument('--freeze',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--kwargs-output',required=True,type=Path)
    a=p.parse_args();g=common.load_freeze(a.freeze)
    _,proof,payload=common.prepare(g)
    a.kwargs_output.write_text(payload+chr(10));assert common.sha(a.kwargs_output)==proof['kwargs_sha256']
    common.write(a.output,proof)
    print(json.dumps({key:proof[key] for key in ('status','label','source_commit','native_config_sha256','recipe_sha256','native_input_sha256','kwargs_sha256','engine_constructors')},sort_keys=True))

if __name__=='__main__':main()
