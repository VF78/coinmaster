"""Bounded report rows only; never purges cache or mutates native state."""
import gzip
import math
import hashlib
import json
from decimal import Decimal
from pathlib import Path

SCHEMA='coinmaster.method-a-risk.v1'


def wire(value):
    if value is None or type(value) in (str,int,bool):return value
    if type(value)is float:
        if not math.isfinite(value):raise ValueError('METHOD_A_NONFINITE_NATIVE_PUBLIC_FLOAT')
        return value
    if isinstance(value,Decimal):
        if not value.is_finite():raise ValueError('METHOD_A_NONFINITE_REPORT')
        return str(value)
    if isinstance(value,(tuple,list)):return [wire(v) for v in value]
    if isinstance(value,dict):return {str(k):wire(v) for k,v in value.items()}
    raise TypeError('METHOD_A_UNKNOWN_REPORT_TYPE:'+type(value).__name__)


class MethodARiskRows:
    def __init__(self,path,kind):
        self.path=Path(path);self.kind=kind;self.count=0;self.closed=False
        if self.path.exists():raise ValueError('METHOD_A_AUDIT_NAMESPACE_EXISTS')
        self.stream=gzip.open(self.path,'wt',compresslevel=1)

    def append(self,row):
        if self.closed:raise ValueError('METHOD_A_AUDIT_CLOSED')
        self.stream.write(json.dumps(wire(row),sort_keys=True,separators=(',',':'))+'\n');self.count+=1

    def __len__(self):return self.count

    def finish(self):
        if not self.closed:self.stream.close();self.closed=True
        digest=hashlib.sha256()
        with self.path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
        return dict(schema=SCHEMA,kind=self.kind,path=str(self.path),rows=self.count,sha256=digest.hexdigest(),completeness='ALL_EMITTED_ROWS_NO_SAMPLING',native_state_mutations=0)
