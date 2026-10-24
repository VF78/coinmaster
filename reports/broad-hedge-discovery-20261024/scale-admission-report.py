from pathlib import Path
from datetime import datetime,timezone
import csv,json,hashlib
O=Path(__file__).resolve().parent
z=json.loads((O/'scale-admission-results.json').read_text());v=json.loads((O/'scale-admission-verification.json').read_text());assert v['status']=='PASS_POST_SELECTION_SCALE_ONLY'
fmt=lambda v:f'{float(v):,.2f}'
report='''# Post-selection scale admission — cache/scalar only

Обычная quantity-fixed половинная SOL-накладка в выбранных B2/4h и F0/8h не объясняет необходимый масштаб роста. Fixed-return transfer даёт примерно137.6–140.2k и110.0–113.6k scalar-equivalent соответственно, против70/90floors4.257m/5.470m. Это не новые candidateTOTAL/ROI или backtests. Сигнал B2 остаётся положительным discovery-направлением; масштаб обычной накладки слишком мал. F0 остаётся protection/control, не источником положительного роста.

Выбор фиксирован после discovery по ранее объявленному ranking: B2/4h capital, F0/8h protection. Новых marks/actions/trade hypotheses/statistical tests нет; исходные36configuration results/phase ledger не менялись. Все4funding/slip cases сохранены отдельно. Arithmetic input/protocol/script hashes записаны до scalar pass.

## Cached endpoint contributions по прежним actual R3 quantities

δ — прежний cached net_H endpoint contribution. A_i — прежний actual R3 pre-cycle flat capital из accepted83cycle ledger. Meanδ/A_i не равна meanδ/NB_t; положительная signal-NB mean не гарантирует положительный cycle-capital-weighted mean. Sumsδ/A_i — сумма разных локальных вкладов, не сложный общий return.

| Rule | Slip bp | Funding | Cohort | n | Sumδ USDT | Meanδ USDT | Sumδ/A_i | Meanδ/A_i % | Meanδ/NB_t bp | Last action endpoint UTC |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|
'''
for r in z['cached_delta_tables']:
 end=datetime.fromtimestamp(int(r['latest_hypothetical_action_endpoint_utc'])/1e9,timezone.utc).isoformat()
 report+=f"| {r['rule']} | {r['slip_bp']} | {r['funding_boundary']} | {r['cohort']} | {r['n']} | {fmt(r['endpoint_delta_sum_USDT'])} | {fmt(r['endpoint_delta_mean_USDT'])} | {float(r['sum_delta_over_original_cycle_A']):.6f} | {float(r['mean_delta_over_original_cycle_A'])*100:.6f} | {float(r['mean_delta_over_NB_t_bp']):.4f} | {end} |\n"
report+='''
В2bp B2 даёт общий endpointδ+18,472.21USDT, из них первый год всего+67.02; meanδ/A_i первого года отрицательна−0.01977%, несмотря на положительную meanδ/NB_t. F0 даёт общий endpointδ−28,094.21…−28,099.51USDT. Early entry cohort endpoint sums B2+1,028.79/F0+4,250.10 — не капитал на15января и не доказанное устранение разрыва с E4: это сумма отдельных endpoint contributions без новой candidate equity trajectory.

## Единственный fixed-return transfer на83cycles

Формула seed×product(1+r_i+δ_i/A_i), δ0если opportunity нет. Исходные quantities/admission/fills и r_i/A_i не пересчитываются; внутрисистемная капитализация, timing, paired reductions/3TP/capacity/lifecycle не моделируются. Scalar-equivalent НЕnativeTOTAL/actualcandidateROI. В каждой строке отдельный coherent case, не выбран лучший.

| Rule | Slip bp | Funding | Scalar-equivalent | S0 net retention % | Gap70 USDT | Gap90 USDT | Needed terminal multiplier70/90 |
|---|---:|---|---:|---:|---:|---:|---:|
'''
for r in z['fixed_transfer_products']:
 report+=f"| {r['rule']} | {r['slip_bp']} | {r['funding_boundary']} | {fmt(r['terminal_scalar_equivalent'])} | {float(r['net_profit_retention_pct_vs_legacyS0']):.4f} | {fmt(r['gap70_USDT'])} | {fmt(r['gap90_USDT'])} | {float(r['required_terminal_multiple70']):.3f}/{float(r['required_terminal_multiple90']):.3f} |\n"
report+='''
Для B2 остаётся примерно30–31× до70floor и39–40× до90; для F0 примерно37–39×/48–50×. Это масштабный разрыв при фиксированном transfer assumption, не формальный upper bound всех SOL/изменённых BTC exits.

## Oracle coverage-only bookend

Только covered ORIGINAL future losing cycles получают r_i0; ALL winners сохранены, uncovered losers неизменны. Future loser labels никогда не становятся signal features. UNION — только множество coveredcycles для oracle, НЕunioncash/combinedstrategy/best-action selection. Числа не подтверждают реализуемый выход и не являются общей границей всего SOL/изменённого BTC lifecycle.

| Coverage | Covered83 cycles | Covered29 losers | Covered negative log loss % | Scalar-equivalent | S0 net retention % | Gap70 USDT | Gap90 USDT |
|---|---:|---:|---:|---:|---:|---:|---:|
'''
for r in z['oracle_coverage']:
 report+=f"| {r['coverage_set']} | {r['covered_cycles']} | {r['covered_losing_cycles']} | {float(r['covered_negative_log_return_fraction'])*100:.4f} | {fmt(r['terminal_scalar_equivalent'])} | {float(r['net_profit_retention_pct_vs_legacyS0']):.4f} | {fmt(r['gap70_USDT'])} | {fmt(r['gap90_USDT'])} |\n"
report+='''
Даже идеальное удаление всех covered losers каждого сигнала по отдельности с сохранением ALL winners не достигает70floor: B2 oracle≈946k, F0≈3.577m. У F0 всё ещё680k gap70/1.894m gap90. Coverage union oracle≈6.257m превышает оба floor, но требует28из29future losses обнулить и сохранить всех winners; это только демонстрация ширины покрытия и предельно сильного future-knowing attenuation assumption. Обычная halfSOL накладка не воспроизводит этот oracle. Для native-кандидата нужен отдельно обоснованный причинный механизм paired risk exit/другой источник роста; существующие local bp сами это не доказывают.

## Верификация, scope и артефакты

Один cache/scalar pass + одна independent verification PASS:32exact cache sum/mean/δA tables,8Fraction transfer products,3Fraction oracle products/gaps; independent float log1p coverage совпала с Decimal ln. Новых trade outcomes/configurations/native/engine runs0. Source/discovery/phase hashes неизменны. No candidateTOTAL/globalDD/70-90 proof, no new product/native budget.

Сохранён schema note: в первоначальном cached-delta CSV column latest_hypothetical_action_endpoint_utc содержит integer nanoseconds; это endpoint_ns, не formatted UTC. В таблице выше преобразовано в UTC; исходный receipt сохранён, money не изменены.

Artifacts:scale-admission-results.json; scale-admission-cached-deltas.csv; scale-admission-fixed-transfer.csv; scale-admission-oracle-coverage.csv; scale-admission-verification.json; scale-admission-ledger.json. Статистические p и discovery results не менялись.
'''
(O/'scale-admission-report.md').write_text(report);l=json.loads((O/'scale-admission-ledger.json').read_text());l['report_sha256']=hashlib.sha256((O/'scale-admission-report.md').read_bytes()).hexdigest();(O/'scale-admission-ledger.json').write_text(json.dumps(l,indent=2)+'\n');print(l['report_sha256'])
