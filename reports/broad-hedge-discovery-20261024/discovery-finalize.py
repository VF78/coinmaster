"""Report complete frozen library; no new hypotheses/performance labels."""
from pathlib import Path
from datetime import datetime,timezone
import csv,json,hashlib,collections
O=Path(__file__).resolve().parent
read=lambda p:list(csv.DictReader(Path(p).open()))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ledger=json.loads((O/'phase-ledger.json').read_text());assert ledger['stage_I']['verification_status']=='PASS' and ledger['stage_II']['verification_status']=='PASS'
configs=read(O/'discovery-combined-configurations.csv');assert len(configs)==36
episodes=read(O/'discovery-stageI-episodes.csv')+read(O/'discovery-stageII-episodes.csv');attempts=read(O/'discovery-stageI-entry-attempts.csv')
yes=lambda x:str(x)=='True'
def num(v):return f'{float(v):.3f}' if str(v) else 'NA'
positives=[s for s in configs if yes(s['qualified_raw_capital']) or yes(s['qualified_raw_protection'])];sparse=[s for s in configs if yes(s['sparse'])];rawcontrol=[s for s in configs if (yes(s['raw_capital_positive']) or yes(s['raw_protection_positive'])) and not yes(s['true_SOL_eligible'])]
report='''# Broad saved-data discovery — 36 configurations, no confirmed candidate

Библиотека завершена: Stage I 16 rules×4h/24h=32 configurations; условный Stage II только B2/F0×8h/12h=4. Всего 7,352 episode/scenario rows. Это сохранённые данные и local attribution, не native/full/short backtests. Физических engine runs, product/pilot/production changes: 0.

Сырые положительные направления: B2 failed favorable break (capital + protection), P1 initial-fill underwater (protection), F0 carry control (protection). Ни один тест не подтверждён после Holm128: все adjusted p=1. Не заявлены candidateTOTAL/globalDD/70%-90% retention/native3TP или causal execution.

## Неизменная бухгалтерия и gates

C* terminal точно120718.40416503, q=0, actual persisted BTC funding4063.32156049, Decimal residual0. C* — settlement-equivalent pricecash, не native futures wallet cash при held position. Wraw=C*+actualq×raw completed mark — наблюдаемая reference attribution. Нового candidate capital/OMS/matching нет.

Размеры/J-budget известны на t; exact same quantity/side guard на e=t+60s, без future-min/re-sizing. Comparator cap — UNKNOWN/noaction при превышении held BTC, не clipping. Source/freeze hashes проверены перед START. Entry funding calendar ties0. Wraw_start всегда factual baseline after all actual flows at e, pre-hypothetical action. NOACTION одинаков во всех сценариях. Actual funding/native fill-prefix ambiguity имеет фиксированную одинаковую baseline bracket; BEFORE/AFTER меняет только hypothetical funding exposure.

Raw gates требуют все три когорты year1/year2/early и все четыре согласованных сценария 0/2bp×BEFORE_ALL/AFTER_ALL. Loss CVaR20 — mean largest ceil(.2n) неотрицательных worst losses FROM ENTRY START. Sampled peak-to-trough не подменяет критерий. Ниже показаны bp от NB_t, means относятся к2bp/BEFORE_ALL; qualification проверена во всех четырёх сценариях.

## Сырые положительные configurations

| Rule/h | n y1/y2/early | Mean H bp y1/y2/early | Mean H−trim bp y1/y2/early | min main CVaR gain vs baseline bp | Raw lanes | Route | raw p capital/protection | Holm128 |
|---|---:|---:|---:|---:|---|---|---:|---:|
'''
for s in positives:
 lanes='/'.join(k for k in ['capital','protection'] if yes(s['qualified_raw_'+k]));report+=f"| {s['rule']}/{s['horizon_h']} | {s['year1_n']}/{s['year2_n']}/{s['early_n']} | {'/'.join(num(s[c+'_mean_H']) for c in ['year1','year2','early'])} | {'/'.join(num(s[c+'_mean_paired']) for c in ['year1','year2','early'])} | {num(s['min_main_CVaR_gain'])} | {lanes} | {s['consistent_route']} | {num(s['capital_p'])}/{num(s['protection_p'])} | 1 |\n"
report+='''
Stage II выбор зафиксирован ДО labels: capital B2/4 имел лучший minimum main paired mean; protection F0/4 имел наибольший minimum main CVaR gain×coverage среди другого семейства. P1 положителен, но не выбран, не заменён постфактум. F0 — известный carry/protection control, не новая funding alpha. У B2/8 и12 protection проходит RETURN, несмотря на худший tail против trim в одной основной когорте; маршруты не смешаны между годами. B2/4 проходит оба маршрута.

Исходные B2/24 и F0/24 не проходят; F0/12 тоже не проходит. Stage II повторно использует историю, не OOS. Больше horizons/thresholds/sizes/TP tuning этим бюджетом не разрешено.

## Вся сетка, включая пустые и неудачные

min ΔtailN = minimum CVaR_N−CVaR_H по двум основным годам и всем4scenarios; min ΔtailT = CVaR_T−CVaR_H. Baseline-tail gain сам по себе недостаточен для qualification.

| Rule | h | n y1/y2/early | H mean bp y1/y2 | H−trim mean bp y1/y2 | min ΔtailN bp | min ΔtailT bp | Status |
|---|---:|---:|---:|---:|---:|---:|---|
'''
for s in configs:
 status='EMPTY' if int(s['episodes'])==0 else 'SPARSE_DESCRIPTIVE' if yes(s['sparse']) else 'RAW_CAPITAL+PROTECTION' if yes(s['qualified_raw_capital']) and yes(s['qualified_raw_protection']) else 'RAW_CAPITAL' if yes(s['qualified_raw_capital']) else 'RAW_PROTECTION' if yes(s['qualified_raw_protection']) else 'CONTROL_RAW_PROTECTION' if yes(s['raw_protection_positive']) else 'FAIL'
 report+=f"| {s['rule']} | {s['horizon_h']} | {s['year1_n']}/{s['year2_n']}/{s['early_n']} | {num(s['year1_mean_H'])}/{num(s['year2_mean_H'])} | {num(s['year1_mean_paired'])}/{num(s['year2_mean_paired'])} | {num(s['min_main_CVaR_gain'])} | {num(s['min_main_CVaR_vs_trim_gain'])} | {status} |\n"
report+='''
## Coverage и известные controls

Все83actual R3 episodes сохранены. 81имеет held completed-H4 opportunity; cycles23/26 flat до следующего H4 и честно noaction. 1,618held raw states/1,584common-valid. Causal D1cov30_lag1D доступен с раннего сентября; первые4цикла не исключены H1lag720-фильтром. H1lag720 только provenance/control. A0 покрывает41/40year episodes и19early. У каждого rule первый valid opportunity/episode, без будущего best entry/re-add.

M1/4 и24 — raw protection positives, но SPARSE12/9/5: minimum10во втором году не выполнен, refinement не назначен. C2 иL1 пустые; thresholds/history не изменены ради событий. A0/4 — raw protection control, не true-SOL admission. A1,R1/R2,F0 сохраняют статус заранее зарегистрированных известных семейств. J2 не прошёл ни один horizon; emergency pure trim/held-only stress не выдан за full-controller proof, pending risk UNKNOWN.

## Экономические и execution ограничения

IDEAL_SYNCHRONOUS_PAIRED_ATTRIBUTION сокращает SOL вместе с observed BTC reductions на raw completed execution close того же timestamp. Это оптимистичная описательная paired assumption, не доказанная реактивная сделка/atomic actual3TP. Latency, partial/late fills, margin, capacity/L2 и полный pending/order risk UNKNOWN. Actual BTC adds остаются baseline и не увеличивают overlay.

Native exit cash/fees кредитованы пропорционально actual reductions; scheduled still-held BTC restoration платит taker; при actual flat BTC не переоткрывается. Hypothetical avoided BTC funding — market-reference attribution, не exact native avoided cash при callback/price-rounding ambiguity. Before/after не являются полной границей всех mixed callback orders. Raw-mark grid/bracketed group boundaries не доказывают intraminute coherent native/event DD. Старый #133 UNKNOWN_DATA_CLOCK_TERMINAL_ENDPOINT не переписан. CandidateTOTAL, reinvestment path, native3TP и восстановление S0capital здесь не вычислены.

## Проверка и использованный бюджет

Stage I independent prefix-event algebra:6,528endpoints/19,584loss metrics/58,752cost-funding components/336cohort means-CVaR/32all3×4gates. Max cash residual2.33e−10USDT, loss5.43e−12bp. Проверены B8192/stored IUT/2-route arithmetic; Stage I RNG draws отдельно не переигрывались.

Stage II independent algebra:824endpoints/2,472losses/7,416components/48cohort tables/4gates. Все36bootstrap cells×8192monthly draws/144contrasts p-CI независимо воспроизведены; combined Holm128 перепроверен. Max cash residual1.16e−10USDT, loss4.86e−12bp. Label/calculation functions в financial verifier не импортировались.

Financial corrections/failures0. Сохранены prelabel failures:лишняя скобка до data build и ошибочный verifier strict-flat assertion; feature money/outcomes ими не исправлялись. Before-review draft features/code/metadata сохранены. Frozen source/data/native artifacts не изменены.

32/32Stage I и4/4условного Stage II завершены, по одной connected verification PASS. Дополнительных configurations/engine/full/short/training/product runs0. Следующий native/full/short или parameter-search budget не открыт. Все36configurations, все сценарии, пустые cells и статистическая неопределённость сохранены, не только положительные.

Artifacts:discovery-combined-configurations.csv; discovery-stageI/II-episodes.csv; discovery-stageI/II-cohorts.csv; discovery-stageI/II-statistics.csv; discovery-stageI/II-verification.json; phase-ledger.json.
'''
(O/'discovery-report.md').write_text(report)
summary={'status':'COMPLETE_DISCOVERY_RAW_POSITIVES_NOT_CONFIRMED','configurations':36,'stageI_configurations':32,'stageII_configurations':4,'scenario_episode_rows':len(episodes),'qualified_raw_capital':[s['rule']+'/'+s['horizon_h'] for s in configs if yes(s['qualified_raw_capital'])],'qualified_raw_protection':[s['rule']+'/'+s['horizon_h'] for s in configs if yes(s['qualified_raw_protection'])],'qualified_raw_families':sorted({s['family'] for s in positives}),'confirmed_configurations':[],'sparse_configurations':[s['rule']+'/'+s['horizon_h'] for s in sparse],'known_control_raw_positive':[s['rule']+'/'+s['horizon_h'] for s in rawcontrol],'entry_attempt_status_counts':dict(collections.Counter(a['status'] for a in attempts)),'actual_cycles':83,'cycles_with_H4':81,'no_H4_cycles':[23,26],'first4Septembercycles_not_H1filtered':True,'all12freeze_pins_intact':all(sha(O/p)==s for p,s in ledger['sha256'].items()),'physical_native_full_short_training_simulator_runs':0,'financial_corrections':0,'financial_failures':0,'further_config_budget':0,'report_sha256':sha(O/'discovery-report.md'),'combined_sha256':sha(O/'discovery-combined-configurations.csv')}
(O/'discovery-summary.json').write_text(json.dumps(summary,indent=2)+'\n');ledger.update(status='COMPLETE_DISCOVERY_RAW_POSITIVES_NOT_CONFIRMED',completed_utc=datetime.now(timezone.utc).isoformat(),total_configurations_evaluated=36,final_summary_sha256=sha(O/'discovery-summary.json'),financial_corrections=0,new_engine_runs=0,next_native_admission='NONE; requires separate concrete protocol/review/budget',next_config_evaluations_authorized=0);(O/'phase-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');print(json.dumps(summary,indent=2))
