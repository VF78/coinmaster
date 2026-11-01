"""Namespaced domain checkpoint bytes in the existing native event journal.

No account reconstruction, order execution or financial calculations.
"""
from dataclasses import asdict,is_dataclass
from decimal import Decimal
from hashlib import sha256
import json

KEY="cm2-btc-reference-v1"
SCHEMA="CM2_BTC_REFERENCE_NATIVE_CONTINUITY_V1"

def encode(value):
    if isinstance(value,Decimal): return {"decimal":str(value)}
    if is_dataclass(value): return encode(asdict(value))
    if isinstance(value,dict): return {str(k):encode(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [encode(v) for v in value]
    if value is None or type(value) in (str,int,float,bool): return value
    raise TypeError("CM2_CHECKPOINT_UNSUPPORTED_TYPE:"+type(value).__name__)

def decode(value):
    if isinstance(value,dict):
        if set(value)=={"decimal"}:
            result=Decimal(value["decimal"])
            if not result.is_finite(): raise ValueError("CM2_CHECKPOINT_NONFINITE")
            return result
        return {k:decode(v) for k,v in value.items()}
    if isinstance(value,list): return [decode(v) for v in value]
    return value

def canonical(value):
    return json.dumps(encode(value),sort_keys=True,separators=(",",":"),allow_nan=False).encode()

class NativeCheckpointStore:
    """CAS/idempotent BLOB persistence; separate table, same native journal."""
    def __init__(self,journal):
        self.db=journal.db
        self.db.execute("CREATE TABLE IF NOT EXISTS cm2_domain_checkpoint (name TEXT PRIMARY KEY,revision INTEGER NOT NULL,body BLOB NOT NULL,sha256 TEXT NOT NULL)")
        self.db.commit()
    def read(self):
        row=self.db.execute("SELECT revision,body,sha256 FROM cm2_domain_checkpoint WHERE name=?",(KEY,)).fetchone()
        if row is None: return None
        revision,body,digest=row
        body=bytes(body)
        if sha256(body).hexdigest()!=digest: raise ValueError("CM2_CHECKPOINT_INTEGRITY")
        return int(revision),body
    def persist(self,body,expected_revision):
        if type(body) is not bytes or not body or type(expected_revision) is not int:
            raise ValueError("CM2_CHECKPOINT_INVALID_CAS")
        if self.db.in_transaction: raise ValueError("CM2_CHECKPOINT_FOREIGN_TRANSACTION")
        try:
            self.db.execute("BEGIN IMMEDIATE")
            previous=self.read()
            revision=previous[0] if previous else 0
            if revision!=expected_revision:
                self.db.rollback();return None
            if previous is not None and previous[1]==body:
                self.db.commit();return revision
            revision+=1
            self.db.execute("INSERT OR REPLACE INTO cm2_domain_checkpoint VALUES (?,?,?,?)",
                (KEY,revision,body,sha256(body).hexdigest()))
            self.db.commit();return revision
        except BaseException:
            self.db.rollback();raise

def observer_continuity(recorder,observer):
    """Read existing tracker internals without finalizing/mutating summaries."""
    if recorder is None or observer is None: raise ValueError("CM2_NATIVE_OBSERVER_CONTINUITY_REQUIRED")
    return {"minute":{"rows":recorder.rows,"fill_epoch":recorder.fill_epoch,
        "curves":{k:vars(v).copy() for k,v in recorder.curves.items()},
        "settled":vars(recorder.settled_curve).copy()},
        "coherent":{"sequence":observer.sequence,"epoch":observer.epoch,
        "initial_seed":observer.initial_cash,"events":vars(observer.events).copy(),
        "settled":vars(observer.settled).copy(),"seen_fills":sorted(observer.seen_fills)}}
