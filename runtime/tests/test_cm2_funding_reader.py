"""Exact native-audit cache parity. Synthetic SQLite rows; no engine/account."""
from decimal import Decimal as D,localcontext,ROUND_HALF_EVEN,ROUND_DOWN,Inexact,Rounded,InvalidOperation
from pathlib import Path
import sqlite3
from types import SimpleNamespace as N
import pytest
from coinmaster.ledger.journal import NativeEventJournal
from coinmaster.research.cm2_funding_reader import NativeSignedFundingReader

BTC="BTC-USD-PERP.HYPERLIQUID"
SOL="SOL-USD-PERP.HYPERLIQUID"

class CountJournal(NativeEventJournal):
    calls=0
    def funding_cash_audit(self):
        self.calls+=1
        return super().funding_cash_audit()

def original(journal,asset):
    return sum((D(r[5]) for r in NativeEventJournal.funding_cash_audit(journal) if r[1]==str(asset)),D(0)) if journal else D(0)

def row(journal,event,asset,when,delta):
    journal.record_funding_cash(event,asset,when,D(10000),D(10000)+D(delta))

def same(reader,journal):
    for asset in (BTC,SOL,"ABSENT"):
        assert reader(asset).as_tuple()==original(journal,asset).as_tuple()

def test_none_and_repeated_assets_preserve_zero_and_one_sorted_audit_read():
    assert NativeSignedFundingReader(None)(BTC)==original(None,BTC)
    j=CountJournal()
    try:
        row(j,"b",BTC,2,"-1");row(j,"a",SOL,1,"2")
        r=NativeSignedFundingReader(j);same(r,j)
        for _ in range(100):same(r,j)
        assert j.calls==1
    finally:j.close()

def test_own_append_backdated_duplicate_update_delete_and_other_table_commit():
    j=CountJournal()
    try:
        row(j,"later",BTC,20,".12345678");row(j,"sol",SOL,10,"-.5")
        r=NativeSignedFundingReader(j);same(r,j)
        row(j,"earlier",BTC,1,"-2");same(r,j)
        calls=j.calls
        row(j,"earlier",BTC,1,"999")  # actual INSERT OR IGNORE
        same(r,j);assert j.calls==calls
        j.db.execute("UPDATE funding_cash SET signed_delta='3.00000000',before_total='10000',after_total='10003' WHERE event_id='earlier'")
        j.db.commit();same(r,j)
        j.db.execute("DELETE FROM funding_cash WHERE event_id='later'");j.db.commit();same(r,j)
        j.record_transfer("metadata",D(10),D(5),D(0),D(5));same(r,j)
    finally:j.close()

def test_transactions_savepoint_rollback_and_postrollback_cache_are_exact():
    j=CountJournal()
    try:
        row(j,"base",BTC,1,"1")
        r=NativeSignedFundingReader(j);same(r,j)
        j.db.execute("BEGIN")
        j.db.execute("INSERT INTO funding_cash VALUES (?,?,?,?,?,?)",("outer",BTC,2,"10000","10002","2"))
        same(r,j)
        j.db.execute("SAVEPOINT inner")
        j.db.execute("UPDATE funding_cash SET signed_delta='9' WHERE event_id='base'")
        same(r,j)
        j.db.execute("ROLLBACK TO inner");same(r,j)
        j.db.execute("RELEASE inner");same(r,j)
        j.db.rollback();same(r,j)
        assert r(BTC)==D(1)
    finally:j.close()

def test_rolledback_change_without_intermediate_read_never_returns_stale_value():
    j=CountJournal()
    try:
        row(j,"base",BTC,1,"1");r=NativeSignedFundingReader(j);same(r,j)
        j.db.execute("UPDATE funding_cash SET signed_delta='500' WHERE event_id='base'")
        j.db.rollback();same(r,j)
        assert r(BTC)==D(1)
    finally:j.close()

def test_external_append_update_duplicate_commit_and_rollback(tmp_path):
    j=CountJournal(str(tmp_path/"native.sqlite"));external=sqlite3.connect(tmp_path/"native.sqlite")
    try:
        row(j,"base",BTC,1,"1");r=NativeSignedFundingReader(j);same(r,j)
        external.execute("INSERT INTO funding_cash VALUES (?,?,?,?,?,?)",("ext",SOL,2,"10000","9997","-3"))
        external.commit();same(r,j)
        external.execute("UPDATE funding_cash SET signed_delta='4' WHERE event_id='base'")
        external.commit();same(r,j)
        external.execute("INSERT OR IGNORE INTO funding_cash VALUES (?,?,?,?,?,?)",("ext",SOL,2,"0","9","9"))
        external.commit();same(r,j)
        external.execute("UPDATE funding_cash SET signed_delta='500' WHERE event_id='ext'")
        external.rollback();same(r,j)
        assert r(BTC)==D(4) and r(SOL)==D(-3)
    finally:external.close();j.close()

def test_connection_reopen_identity_invalidates_even_when_counters_restart(tmp_path):
    path=tmp_path/"native.sqlite";j=CountJournal(str(path))
    try:
        row(j,"base",BTC,1,"1");r=NativeSignedFundingReader(j);same(r,j)
        before=r._connection
        j.close()
        external=sqlite3.connect(path)
        external.execute("UPDATE funding_cash SET signed_delta='7' WHERE event_id='base'")
        external.commit();external.close()
        j.db=sqlite3.connect(path)
        same(r,j)
        assert r._connection is not before and r(BTC)==D(7)
    finally:j.close()

def test_decimal_context_order_flags_and_cache_hit_signal_replay():
    j=CountJournal()
    try:
        for index,delta in enumerate(("1E+30","1","-1E+30")):
            j.db.execute("INSERT INTO funding_cash VALUES (?,?,?,?,?,?)",(str(index),BTC,index,"0","0",delta))
        j.db.commit();r=NativeSignedFundingReader(j)
        with localcontext() as ctx:
            for precision,rounding in ((28,ROUND_HALF_EVEN),(40,ROUND_HALF_EVEN),(6,ROUND_DOWN)):
                ctx.prec=precision;ctx.rounding=rounding
                ctx.clear_flags();expected=original(j,BTC);flags=dict(ctx.flags)
                ctx.clear_flags();got=r(BTC)
                assert got.as_tuple()==expected.as_tuple() and dict(ctx.flags)==flags
                ctx.clear_flags();again=r(BTC)
                assert again.as_tuple()==expected.as_tuple() and dict(ctx.flags)==flags
            ctx.prec=6;ctx.traps[Inexact]=True
            ctx.clear_flags()
            with pytest.raises(Inexact):original(j,BTC)
            flags=dict(ctx.flags);ctx.clear_flags()
            with pytest.raises(Inexact):r(BTC)
            assert dict(ctx.flags)==flags
    finally:j.close()

def test_unrequested_bad_asset_is_not_eagerly_parsed_and_errors_remain_exact():
    j=CountJournal()
    try:
        row(j,"good",BTC,1,"1")
        j.db.execute("INSERT INTO funding_cash VALUES (?,?,?,?,?,?)",("bad",SOL,2,"0","0","not-a-number"))
        j.db.commit();r=NativeSignedFundingReader(j)
        assert r(BTC)==original(j,BTC)==D(1)
        with pytest.raises(InvalidOperation):original(j,SOL)
        with pytest.raises(InvalidOperation):r(SOL)
    finally:j.close()

def test_actual_parent_funding_delta_method_and_duplicate_callbacks_match():
    from coinmaster.strategy.cm2_native import CM2Strategy
    j=CountJournal()
    try:
        new_reader=NativeSignedFundingReader(j)
        def fake(reader):
            return N(config=N(funding_reader=reader,btc_id=BTC),_btc_cost_qty=D(0),
                _parent_funding=D(0),_funding_last=D(0),_parent_cost_known=True)
        old=fake(lambda asset:original(j,asset));new=fake(new_reader)
        def synchronize():
            for state in (old,new):CM2Strategy._sync_funding(state)
            assert (new._parent_funding,new._funding_last,new._parent_cost_known)==(
                old._parent_funding,old._funding_last,old._parent_cost_known)
        synchronize();old._btc_cost_qty=new._btc_cost_qty=D(40)
        row(j,"btc-a",BTC,1,"-1");synchronize()
        for _ in range(10):synchronize()
        row(j,"sol-a",SOL,1,"3");synchronize()
        row(j,"btc-a",BTC,1,"999");synchronize()
        row(j,"btc-b",BTC,2,"2");synchronize()
        assert new._parent_funding==D(1)
        old._btc_cost_qty=new._btc_cost_qty=D(0)
        old._parent_funding=new._parent_funding=D(0);synchronize()
        old._btc_cost_qty=new._btc_cost_qty=D(10)
        row(j,"btc-c",BTC,3,"-3");synchronize()
        assert new._parent_funding==D(-3)
    finally:j.close()
