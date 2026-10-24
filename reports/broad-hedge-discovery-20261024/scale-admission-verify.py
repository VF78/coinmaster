"""Independent Fraction products/cache sums and float-log coverage checks."""
from pathlib import Path
from fractions import Fraction as Q
from decimal import Decimal as D,getcontext
from datetime import datetime,timezone
import csv,json,hashlib,math,collections
getcontext().prec=90
O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:list(csv.DictReader(Path(p).open()))
ledger=json.loads((O/'scale-admission-ledger.json').read_text());assert ledger['scalar_pass_completed']==1 and not ledger.get('verification_started')
for x in ledger['input_sha256'].values():assert sha(x['path'])==x['sha256']
assert sha(O/'scale-admission-results.json')==ledger['results_sha256']
ledger['verification_started']=1;ledger['verification_start_utc']=datetime.now(timezone.utc).isoformat();(O/'scale-admission-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
result=json.loads((O/'scale-admission-results.json').read_text());growth=json.load(open(ledger['input_sha256']['growth']['path']));cycles=growth['cycle_checks'];orig={int(c['cycle']):c for c in cycles};source={rule:[r for r in read(ledger['input_sha256'][name]['path']) if r['rule']==rule and r['horizon_h']==h] for rule,h,name in [('B2','4','stageI_cache'),('F0','8','stageII_cache')]};sets={rule:{int(r['cycle']) for r in z} for rule,z in source.items()};sets['UNION']=sets['B2']|sets['F0'];checks=collections.Counter()
def exactD(q):return D(q.numerator)/D(q.denominator)
def close(q,s):assert abs(exactD(q)-D(s))<=max(D('1e-65'),abs(D(s))*D('1e-73')),(exactD(q),s)
for table in result['cached_delta_tables']:
 z=[r for r in source[table['rule']] if r['slip_bp']==table['slip_bp'] and r['funding_boundary']==table['funding_boundary']];c=table['cohort'];z=z if c=='all' else [r for r in z if r['early']=='True'] if c=='early' else [r for r in z if r['year']==c]
 assert len(z)==table['n'];amount=sum((Q(r['net_H']) for r in z),Q(0));parts=sum((Q(r['net_H'])/Q(orig[int(r['cycle'])]['A']) for r in z),Q(0));close(amount,table['endpoint_delta_sum_USDT']);close(amount/len(z),table['endpoint_delta_mean_USDT']);close(parts,table['sum_delta_over_original_cycle_A']);close(parts/len(z),table['mean_delta_over_original_cycle_A']);checks['exact_cache_sum_mean_deltaA_tables']+=1
for row in result['fixed_transfer_products']:
 z=[r for r in source[row['rule']] if r['slip_bp']==row['slip_bp'] and r['funding_boundary']==row['funding_boundary']];delta={int(r['cycle']):Q(r['net_H']) for r in z};value=Q(10000)
 for c in cycles:value*=1+Q(c['return'])+delta.get(int(c['cycle']),Q(0))/Q(c['A'])
 close(value,row['terminal_scalar_equivalent']);close((value-10000)/(Q('6077107.23887483')-10000)*100,row['net_profit_retention_pct_vs_legacyS0']);checks['independent_Fraction_fixed_transfer_products']+=1
alllog=sum(-math.log1p(float(c['return'])) for c in cycles if Q(c['return'])<0)
for row in result['oracle_coverage']:
 cover=sets[row['coverage_set']];assert len(cover)==row['covered_cycles'];value=Q(10000);logcovered=0.;losers=0
 for c in cycles:
  ret=Q(c['return'])
  if int(c['cycle']) in cover and ret<0:logcovered-=math.log1p(float(ret));losers+=1;ret=Q(0)
  value*=1+ret
 close(value,row['terminal_scalar_equivalent']);assert losers==row['covered_losing_cycles'];assert abs(logcovered/alllog-float(row['covered_negative_log_return_fraction']))<2e-14
 for pct,floor in [('70','4256975.067212381'),('90','5470396.514987347')]:close(Q(floor)-value,row['gap'+pct+'_USDT']);close(Q(floor)/value,row['required_terminal_multiple'+pct])
 checks['oracle_Fraction_products_gaps_logcoverage']+=1
assert all(sha(x['path'])==x['sha256'] for x in ledger['input_sha256'].values())
verification={'status':'PASS_POST_SELECTION_SCALE_ONLY','checks':dict(checks),'independent_method':'Exact Fraction cache sums/products/retentions/gaps; independent float log1p coverage vs Decimal ln','original_discovery_and_phase_hashes_unchanged':True,'new_trade_outcomes':0,'new_configurations':0,'native_engine_runs':0,'schema_note':'cached-delta CSV latest_hypothetical_action_endpoint_utc field contains original integer nanoseconds; treat as endpoint_ns, not formatted UTC. Original output preserved, no money effect.','verifier_sha256':sha(Path(__file__))}
(O/'scale-admission-verification.json').write_text(json.dumps(verification,indent=2)+'\n');ledger.update(status='PASS_POST_SELECTION_SCALE_ONLY',verification_completed=1,verification_sha256=sha(O/'scale-admission-verification.json'));(O/'scale-admission-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');print(json.dumps(verification,indent=2))
