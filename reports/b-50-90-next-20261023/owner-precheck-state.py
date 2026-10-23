"""Augment saved-B causal cohort with actual finalized native state, no engine."""
import csv,gzip,json
from pathlib import Path
from decimal import Decimal
R=Path(__file__).parent;J=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023');E=R.parent/'sol-conditional-hedge-btc-band-20261023/owner-BTC_REGIME_REENTRY_BAND_05-events'
rows=list(csv.DictReader((R/'owner-btc-parent-precheck.csv').open()));fills=list(csv.DictReader((E/'native-fill-audit.csv').open()));remaining=list(rows)
with gzip.open(J/'BTC_REGIME_REENTRY_BAND_05/result/minute-native-settled-receipts.csv.gz','rt') as f:
 for sample in csv.DictReader(f):
  source=int(sample['source_quote_ns'])
  while remaining and source>=int(remaining[0]['native_parent_terminal_ns']):
   r=remaining.pop(0);p=json.loads(sample['native_positions_and_mark_ohlc_json']);btc=next((x for x in p if x['instrument_id'].startswith('BTC')),None);sol=next((x for x in p if x['instrument_id'].startswith('SOL')),None)
   r.update(snapshot_source_ns=source,snapshot_receipt_ns=sample['receipt_ns'],native_cash=sample['cash'],native_equity=sample['paired_close_equity'],actual_BTC_open_lots=str(int(Decimal(btc['quantity'])/Decimal('.001'))) if btc else '0',actual_SOL_qty=sol['quantity'] if sol else '0',pending_inflight_increases='UNKNOWN_EXACT_QUEUE_NATIVE_CACHE_SNAPSHOT_NOT_EXPORTED',D1_signal_asof_ns=int(r['start_ns'])//86400000000000*86400000000000,cohort_wave_provenance='EXACT_FROZEN_DOMAIN_COMPLETED_WAVES_AT_RECORDED_DECISION_INDEX',suppression_provenance='FROZEN_SELECTOR_FULL_BRANCH_SUPPRESSES_REAL_ZERO_SLOTS')
for i,r in enumerate(rows):
 end=int(rows[i+1]['start_ns']) if i+1<len(rows) else 1788220800000000000
 r['actual_later_ordinary_tp_filled_lots']=json.dumps({level:sum(int(Decimal(x['qty'])/Decimal('.001')) for x in fills if int(r['start_ns'])<=int(x['fill_ns'])<end and x['action']=='BTC_REDUCE' and x['level']==str(level)) for level in range(3)})
 r['later_recovery']='SAVED_NATIVE_PATH_ONLY_SEE_EPISODE_LEDGER_NO_COUNTERFACTUAL_PROFIT'
keys=list(dict.fromkeys(k for r in rows for k in r))
with (R/'owner-btc-parent-precheck.csv').open('w',newline='') as f:w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)
print('native snapshots',sum('snapshot_source_ns' in x for x in rows),'parents',len(rows))
