"""Actual new typed payload serialization/causal pin rejection; no engine."""
from decimal import Decimal as D
from dataclasses import FrozenInstanceError
import hashlib,json
import msgspec
import pytest
from coinmaster.research.paired_signal_feed import PairedSignal,paired_feed_json_rows


def test_new_typed_payload_decimal_precision_and_json_roundtrip_no_future_resize():
    row=PairedSignal(1725163200000000000,1725163200000000000,1725163260000000000,
        D('58504.3'),D('134'),D('.3770012546978323456712'),D('2.123456789123456789'),
        True,True,False,True,False,D('59000.1'),D('58000.1'),D('58944.4'))
    native_bytes=msgspec.json.encode((row,))
    restored=msgspec.json.decode(native_bytes,type=tuple[PairedSignal,...])
    assert restored==(row,)
    assert json.loads(json.dumps(paired_feed_json_rows(restored)))[0]['a']==str(row.a)
    assert restored[0].owner_row()['PB']==D('58504.3')
    with pytest.raises(FrozenInstanceError):row.btc_close=D(1)
