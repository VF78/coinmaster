from pathlib import Path
from datetime import datetime,timezone
import csv,json,hashlib
O=Path(__file__).resolve().parent
read=lambda p:list(csv.DictReader(Path(p).open()))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=json.loads((O/'capital-alignment-results.json').read_text());v=json.loads((O/'capital-alignment-verification.json').read_text());assert v['status']=='PASS_POST_RESULT_CAPITAL_ALIGNMENT'
summ=read(O/'capital-alignment-summary.csv');coh=read(O/'capital-alignment-cohorts.csv');bounds=read(O/'capital-alignment-boundaries.csv');paths=read(O/'capital-alignment-paths.csv')
f=lambda x:f'{float(x):,.2f}'
report='''# Capital alignment — all36 cached configurations

POST_RESULT cache/scalar diagnostic завершён, independent Fraction verification PASS. Пересчёт всех36старых configurations×4coherent cases×H/T показал: существенный capital benefit в J2 или других отрицательных поNBmean вариантах не был пропущен. Лучший worst-case scalar-equivalent — B2/12h140,994.14, только2.1591%net profit исходного S0 и gap70≈4.116m. Ни70floor, ни50% даже cycle-boundaryDD здесь не получены. Это conditional scalar arithmetic, не candidateTOTAL/nativebacktest/actualROI/globalmarkedDD/native70/50PASS.

Старые36grid/128inference и pvalues неизменны. Новых marks/entries/actions/horizons/strategy combinations/trade outcomes нет. 288условных H/T paths и23,904cycle factors — арифметическое преобразование cachedδ, не новые торговые configurations. No factor<=0:0infeasible paths, clamp/abs/fake liquidation не применялись.

## Метод и cohorts

Для каждого83original R3cycles используется1+r_i+cachedδH_i/A_i и отдельно1+r_i+cachedδT_i/A_i; δ0для noactioncycle. Сохранены original A_i/r_i, quantities/admission/fills. Внутри-cycle timing/реальный coupledBTC-SOL lifecycle/3TP/capacity/changed compounding не моделируются. Original scalar product120718.40416503 воспроизводится.

Capital scale positive означает cumulative loglift H>0 в year1/year2/early и всех4funding/slip cases. Paired positive — отдельно logliftH−T>0 в техже cells. Рейтинг: worst-case terminalequivalent, затем worst-cohort loglift; этоpost-result estimand, не новое подтверждение discovery-tests/OOS.

Cohorts группируются по ORIGINAL BTC cycle FIRST ACTUAL FILL start:43/40cycles в year1/year2,19early. Noactioncycles входят сδ0. Это отличается от discovery action-entry NBcohorts41/40A0episodes. Для каждого originalcyclecohort опубликованы и meanδ/A_i, и meanδ/NB_t поcovered opportunities. PositiveNBmean, arithmeticmeanδ/A и geometricloglift — разные estimands.

## Полный рейтинг всех36

H — изученная overlay/jointaction; T — её equal-factor trim на техже opportunities. Worst H иworst T могут относиться к разным cases; paired loglift проверяется только на одинаковом coherent case. DD показан исключительно между83scalar cycle boundaries; он НЕglobal marked/eventDD.

| Rank | Rule/h | Covered83 | Worst H equiv | Worst T equiv | H cycleDD worst % | Retention H %S0net | min cohort H loglift | min paired loglift | Hpositive / paired | Tags |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|
'''
for s in summ:
 tags=[]
 if s['known_control']=='True':tags.append('known/control')
 if s['discovery_sparse']=='True':tags.append('sparse' if int(s['covered_cycles']) else 'empty')
 if s['rule']=='J2':tags.append('joint+trim+emergency')
 report+=f"| {s['rank_worst_terminal']} | {s['rule']}/{s['horizon_h']} | {s['covered_cycles']} | {f(s['worst_H_terminal_equiv'])} | {f(s['worst_T_terminal_equiv'])} | {float(s['worst_H_cycleboundary_DD_pct']):.3f} | {float(s['net_retention_at_worst_H_pct']):.4f} | {float(s['worst_H_loglift_cohort']):.6f} | {float(s['worst_paired_loglift_cohort']):.6f} | {s['capital_scale_positive_H_all3x4']}/{s['paired_loglift_positive_HminusT_all3x4']} | {', '.join(tags)} |\n"
report+='''
## Положительные capital-cohort lifts

Только B2/12h,4h,8h и A0/4hcontrol положительны поHиpaired loglift во всех3cohorts×4cases. P1/4h иF0/12h pairedpositive, но Hcapitalpositive не проходят. A0 не стал новым true-SOL candidate. Изменение estimand не переписывает прежние отрицательные raw/discovery tests.

Ниже logliftminimum по4cases; meanδ/A_all и meanδ/NB — строго2bp/BEFORE_ALL, не лучший подобранныйcase. Meanδ/A_all включает noactioncycles0; NBmean вычислена только поcovered opportunities.

| Rule/h | Original cohort | all/covered cycles | min H loglift | min paired loglift | meanδ/A_all % | meanδ/NB bp covered |
|---|---|---:|---:|---:|---:|---:|
'''
for s in summ:
 if s['capital_scale_positive_H_all3x4']!='True':continue
 for name in ['year1','year2','early']:
  z=[c for c in coh if c['rule']==s['rule'] and c['horizon_h']==s['horizon_h'] and c['action']=='H' and c['cohort']==name];one=next(c for c in z if c['slip_bp']=='2' and c['funding_boundary']=='BEFORE_ALL')
  report+=f"| {s['rule']}/{s['horizon_h']} | {name} | {one['cycles']}/{one['covered_action_cycles']} | {min(float(c['loglift_vs_original']) for c in z):.6f} | {min(float(c['loglift_H_minus_T']) for c in z):.6f} | {float(one['mean_delta_over_original_A_all_cycles'])*100:.6f} | {float(one['mean_delta_over_NB_t_bp_covered']):.4f} |\n"
report+='''
Например, B2/8hyear1 имеет отрицательные NBmean и meanδ/A_i, но положительный geometricloglift: вклад зависит от original baseline factor1+r_i, не только от среднего δ. Именно поэтому objective-alignment был необходим. Масштаб при этом остаётся малым.

## J2 held-risk проверен, не скрыт

J2выбрал42episodes:27JOINT_SOL_TRIM,6TRIM_ONLY_FALLBACK,9INFEASIBLE_FLOOR/emergency fulltrim. Эти типы сохранены, emergency/fallback не выданы за SOLalpha. WorstH scalar J2/4h80,883.69 противT85,548.91; J2/24h69,570.96 противT92,705.61. Hиpaired cohort loglifts не проходят. J2/24hcycleDDworst56.220% нижеoriginal63.115%, но capitalequivalent сильно хуже и50%не достигнут. Pending/execution/actual3TP/increases остаютсяUNKNOWN, это не новый целостныйriskcontroller.

Самая малая Hcycle-boundaryDD среди всех144cases55.8835%; даже этот грубыйconditional grid не даёт50. Тем более нет доказательства global coherentmarked/eventDD.

## Completed-cycle boundary equivalents

НаJan15/Sep1 учитываются ТОЛЬКОcycles ACTUALLYFLAT строго доboundary. Открытые crossingcycles перечислены и не интерполируются в equity. Finalbenchmarkterminal включает принятуюnative boundary fill. Этоscalarprefix of completed cycles, не cash/equitysnapshot произвольного времени. ВсеH/T/cases сохранены вboundaries.csv; ниже2bp/BEFORE_ALL дляalignmentpositiveиJ2.

| Rule/h | Boundary | Completed cycles | Open crossing cycles | H equiv completed cycles | T equiv completed cycles |
|---|---|---:|---|---:|---:|
'''
for rule,h in [('B2','12'),('B2','4'),('B2','8'),('A0','4'),('J2','4'),('J2','24')]:
 for name in ['early_Jan15','year1_Sep1','benchmark_terminal_post_boundary']:
  z=[b for b in bounds if b['rule']==rule and b['horizon_h']==h and b['slip_bp']=='2' and b['funding_boundary']=='BEFORE_ALL' and b['boundary']==name];Hrow=next(b for b in z if b['action']=='H');Trow=next(b for b in z if b['action']=='T')
  report+=f"| {rule}/{h} | {name} | {Hrow['actual_completed_cycles']} | {Hrow['crossing_open_cycle_ids'] or 'none'} | {f(Hrow['scalar_equivalent_completed_cycles_only'])} | {f(Trow['scalar_equivalent_completed_cycles_only'])} |\n"
report+='''
## Масштаб цели и вывод

ЛучшийB2/12hworstcase:140,994.14equiv, gap70=4,115,980.93 иgap90≈5,329,402.38; netretention2.1591%. Все36 configurations далеки от70/90 и ни одна не даёт50cycleDD. Small positive SOLalpha сам по себе не объясняет нужный growth. Настоящий следующий экономический механизм должен отдельно обосновать существенное изменение BTCheldrisk/pairedexit либо положительныйcashflow при сохранении entryядра. Oracle86%из старых материалов не параметрlive.

Этоpost-resultdescriptive alignment всехcachedвариантов, не основание автоматически просить full/native implementation ради малогоbp. Никакого новогоnative/full/short/training/parameter-search budget этим отчётом не открыто. Actual coupled3TP, latency, margin, capacity/L2, partial/latefills, pendingrisk и новыйlifecycle не доказаны. Pvalues discovery иOOSstatus неизменны.

## Проверка и артефакты

Одинcachepass+одна independent Fraction/moneyverification PASS:23,904exact cycle factors,288products/gaps/retentions/cycleDD,23,904prefix balances,864cohort money/loglifts,864strict completed boundary values,36predicates/ranking. Независимые floatlog calculations согласованы сDecimal80ln. Nonpositivefactors0. New trade outcomes/configurations/native engine runs0. Original discovery/phase/scale/source hashes неизменны, financial corrections0.

Полныеmachine-readable таблицы:capital-alignment-summary.csv(36ranks); paths.csv(288H/Tcases); cohorts.csv(864rows); boundaries.csv(864rows); factors.csv(23,904cycle rows); results.json; verification.json; ledger.json. Отрицательные/empty/sparse/puretrim cases включены.
'''
(O/'capital-alignment-report.md').write_text(report);l=json.loads((O/'capital-alignment-ledger.json').read_text());l['report_sha256']=sha(O/'capital-alignment-report.md');l['status']='COMPLETE_POST_RESULT_CAPITAL_ALIGNMENT_VERIFIED';(O/'capital-alignment-ledger.json').write_text(json.dumps(l,indent=2)+'\n');print(l['report_sha256'])
