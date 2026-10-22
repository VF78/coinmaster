"""Export frozen results only. Never score, call models or read price paths."""
import csv, hashlib, json, tarfile
from pathlib import Path
from datetime import datetime, timezone
BASE=Path(__file__).resolve().parent
RESULT=BASE/'frozen/evaluation-results.json'
PIN='bb056b3e297b93cb5e28238895b5e2501b698811582bceb2fa3a9eef80a7e72d'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(RESULT)==PIN
r=json.loads(RESULT.read_text()); f=json.loads((BASE/'frozen/freeze.json').read_text()); seal=json.loads((BASE/'frozen/evaluation-sealed.json').read_text())
assert len(r['cases'])==24 and len(seal['records'])==48
assert sha(BASE/'frozen/freeze.json') == seal['freeze_sha256']
raw_verified=0
for phase,n in [('debug',10),('evaluation',48)]:
    receipt=json.loads((BASE/f'frozen/{phase}-sealed.json').read_text())
    assert receipt['count']==n and receipt['valid']==n and len(receipt['records'])==n
    for rec in receipt['records']:
        assert sha(BASE/'raw-responses'/f"{rec['window_id']}{rec['arm']}.json")==rec['sha256']
        raw_verified+=1
assert raw_verified==58
assert sha(BASE/'frozen/prompt.json')==f['prompt_sha256']
assert sha(BASE/'frozen/response-schema.json')==f['schema_sha256']
packet_files_verified=0
with tarfile.open(BASE/'frozen-input-packets.tar.gz') as archive:
    members={m.name.removeprefix('./'):m for m in archive.getmembers()}
    for row in f['rows']:
        for arm,pins in row.get('packets',{}).items():
            for name,pin in pins.items():
                path=f"{row['window_id']}{arm}/{name}"
                assert hashlib.sha256(archive.extractfile(members[path]).read()).hexdigest()==pin
                packet_files_verified+=1
assert packet_files_verified==87
rows={x['window_id']:x for x in f['rows'] if x['phase']=='evaluation'}
records={(x['window_id'],x['arm']):x for x in seal['records']}
def utc(t):return datetime.fromtimestamp(t/1000,timezone.utc).isoformat()
case_rows=[];detail_rows=[]
for c in sorted(r['cases'],key=lambda x:x['origin']):
    w=c['window_id']; t=c['truth']
    for arm in ('P','C','prior'):
        a=c['forecasts'][arm];d=a['display']
        if arm=='prior':
            src=rows[w]['prior']; p=src['D'];q=src['Q'];touch=src['touch']
        else:
            raw=BASE/'raw-responses'/f'{w}{arm}.json';assert sha(raw)==records[w,arm]['sha256']
            src=json.loads(raw.read_text());p=src['D']
            q=[[[src['forecasts'][side][sl][k] for k in ('q20','q50','q80')] for sl in ('sl_075','sl_100','sl_150')] for side in ('long','short')]
            touch=[[src['forecasts'][side][sl]['p_adverse_touch'] for sl in ('sl_075','sl_100','sl_150')] for side in ('long','short')]
        case_rows.append(dict(id=c['id'],window_id=w,fold=c['fold'],origin_ms=c['origin'],origin_utc=utc(c['origin']),arm=arm,valid=a['valid'],fallback_to_prior=not a['valid'],cross_SL_incoherent=a['cross_SL_incoherent'],D_UP=p[0],D_DOWN=p[1],D_NONE=p[2],D_truth=t['D'],D_correct=a['loss']['D_correct'],D_logloss=a['loss']['D_logloss'],TP_pinball=a['loss']['TP'],TP_upper_pinball=a['upper_sensitivity']['TP'],SL_Brier=a['loss']['SL'],display_status=d['status'],display_reason=d.get('reason',''),display_side=d.get('side',''),display_SL=d.get('SL',''),display_TP1=d.get('TP',['','',''])[0],display_TP2=d.get('TP',['','',''])[1],display_TP3=d.get('TP',['','',''])[2]))
        for si,side in enumerate(('long','short')):
            for sj,sl in enumerate((.75,1.,1.5)):
                lo,hi=t['Q'][si][sj];qq=q[si][sj]
                dr=dict(id=c['id'],window_id=w,fold=c['fold'],origin_utc=utc(c['origin']),arm=arm,side=side,SL_sigma72=sl,valid=a['valid'],q20=qq[0],q50=qq[1],q80=qq[2],truth_lower=lo,truth_upper=hi,p_full72h_adverse_touch=touch[si][sj],truth_full72h_adverse_touch=t['touch'][si][sj],TP_pinball=a['loss']['TP_rows'][si][sj],TP_upper_pinball=a['upper_sensitivity']['TP_rows'][si][sj],SL_Brier=a['loss']['SL_rows'][si][sj],selected_display_row=d['status']=='DISPLAY' and d['side']==side and d['SL']==sl)
                for k,v in zip(('TP1','TP2','TP3'),qq):
                    dr.update({f'{k}_positive_denominator':int(v>0),f'{k}_zero_forecast':int(v==0),f'{k}_attained_lower':int(v>0 and lo>=v),f'{k}_attained_upper':int(v>0 and hi>=v),f'{k}_quantile_coverage_lower_truth_inclusive':int(lo<=v),f'{k}_quantile_coverage_upper_truth_inclusive':int(hi<=v),f'{k}_quantile_coverage_lower_truth_strict':int(lo<v),f'{k}_quantile_coverage_upper_truth_strict':int(hi<v)})
                detail_rows.append(dr)
def csvwrite(name,data):
    with (BASE/name).open('w',newline='') as out:
        wr=csv.DictWriter(out,fieldnames=list(data[0]));wr.writeheader();wr.writerows(data)
csvwrite('cases.csv',case_rows);csvwrite('forecast-details.csv',detail_rows)
assert len(case_rows)==72 and len(detail_rows)==432
summary={k:r[k] for k in ('status','exploratory_signal','window_bundle_incremental','ambiguous_D','comparisons','economic_evaluation')}
summary.update(result_sha256=PIN,evaluation_windows=24,responses={'debug':10,'evaluation':48,'total':58,'retries':0},history_days=699,original_OOF_ids=8496,horizon_hours=72,csv_rows={'cases.csv':72,'forecast-details.csv':432},metrics={})
for arm,m in r['metrics'].items():
    summary['metrics'][arm]=m.copy()
    summary['metrics'][arm]['SL1_attainment']={side:{k:m[k][si][1] for k in ('TP_attained_lower','TP_attained_upper','TP_positive_denominators','TP_zero_counts')} for si,side in enumerate(('long','short'))}
summary['hash_verification']={'result':'PASS','freeze_against_evaluation_seal':'PASS','raw_answers':'PASS','raw_answers_verified':raw_verified,'prompt_and_schema':'PASS','archive_packet_files':'PASS','archive_packet_files_verified':packet_files_verified,'input_archive_sha256':sha(BASE/'frozen-input-packets.tar.gz')}
summary['responses']['prompt_revisions']=0
summary['quantile_coverage_definition']='Inclusive F(q)=P(Y<=q); interval truth gives certain upper_truth<=q and possible lower_truth<=q. Strict coverage is also retained for atoms. Denominator is all 24 windows, including zero forecasts.'
summary['quantile_coverage_counts']=[]
for arm in ('P','C','prior'):
    for side in ('long','short'):
        for sl in (.75,1.,1.5):
            ds=[x for x in detail_rows if x['arm']==arm and x['side']==side and x['SL_sigma72']==sl]
            summary['quantile_coverage_counts'].append(dict(arm=arm,side=side,SL_sigma72=sl,n=len(ds),counts={k:sum(x[k] for x in ds) for k in ds[0] if 'quantile_coverage' in k}))
(BASE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
lines=['# Результаты ограниченного in-app сравнения BTC, 22 октября 2026','',
'**FEASIBILITY_PASS; EXPLORATORY_SIGNAL = false; window_bundle_incremental = false.** Формат и сбор прошли успешно, однако заданные критерии качества не выполнены. Убедительного преимущества P перед эмпирическим prior и добавочной пользы оконного bundle перед C в этом опыте не установлено.','',
'Полная история DEVELOPMENT за 699 дней и все 8 496 исходных OOF ID сохранены. Здесь оценены только 24 заранее выбранных окна (8 в каждом F1/F2/F3), горизонт H=72 часа; это не полный исторический прогон. Будущие 72-часовые интервалы выбранных окон не перекрываются, но входные истории могут перекрываться, и случаи нельзя считать независимыми. Всего 58 ответов: 10 debug + 48 evaluation (24 пары P/C), без повторных попыток и исправлений. Июльское debug-окно пропущено по LOW_SUPPORT (3 из требуемых 4 примеров), без замены; prompt не пересматривался. Все 48 evaluation-ответов запечатаны до раскрытия query truth и однократного scoring.','',
'P и C — свежие in-app GPT-6.1 Sol / high с одинаковыми 12 полями контекста и теми же четырьмя зрелыми примерами. P дополнительно получил числовые окна query/примеров и график query; C — только контекст и исходы примеров. Поэтому P−C относится ко всему bundle и не выделяет эффект картинки. Prior использует весь причинно допустимый prefix: эмпирические частоты и линейные квантили.','',
'## Первичные потери и направление','',
'TP — средний pinball по 18 квантилям q20/q50/q80, двум сторонам и SL=.75/1/1.5, в σ72, на консервативной lower truth. SL — средний Brier по шести безусловным adverse-touch событиям. Для обеих потерь меньше — лучше. Все выданные прогнозы включены, в том числе NO_TRADE.','',
'| Arm | TP pinball ↓ | SL Brier ↓ | D accuracy | D logloss ↓ | Coverage |','|---|---:|---:|---:|---:|---:|']
for arm,m in r['metrics'].items():
    lines.append(f"| {arm} | {m['all_ID']['TP']:.6f} | {m['all_ID']['SL']:.6f} | {round(m['D_accuracy']*24)}/24 ({m['D_accuracy']:.1%}) | {m['D_logloss']:.6f} | 24/24 |")
lines+=['','D означает первый барьер +1σ72 / −1σ72 / NONE в пределах 72 часов. Неоднозначных D: 0. Ошибок формата, abstain/fallback и cross-SL incoherence: 0 в обеих модельных ветках; all-ID и covered-only совпадают.','',
'## Парные сравнения','',
'Δ = P − reference; отрицательное значение лучше. 95% интервалы: парный bootstrap занятых UTC календарных блоков с якорем Unix epoch, внутри каждого fold; pooled case-weighted mean, 1 000 повторов, seed=7. Это описательные интервалы для малой выборки. Занятых блоков: 14d — 8/8/8 (24 всего); 28d — 5/5/5 (15 всего).','',
'| Reference / score | Δ | 14d 95% CI | Δ F1 / F2 / F3 | 28d 95% CI |','|---|---:|---|---|---|']
for ref,comp in r['comparisons'].items():
    for task,x in comp.items():
        a=x['primary_14d'];b=x['sensitivity_28d'];fold=' / '.join(f'{v:+.6f}' for v in a['fold_means'].values())
        lines.append(f"| {ref} / {task} | {a['mean']:+.6f} | [{a['lower']:+.6f}, {a['upper']:+.6f}] | {fold} | [{b['lower']:+.6f}, {b['upper']:+.6f}] |")
lines+=['','Все четыре первичных 14d интервала включают ноль. P улучшает TP против prior только в 1/3 folds; SL против prior также в 1/3, причём средняя SL потеря выше prior. Против C средние обеих потерь ниже и улучшение есть в 2/3 folds, но оба первичных интервала включают ноль. Только TP против C в 28d sensitivity имеет верхнюю границу ниже нуля; это не заменяет провал первичного 14d критерия и второго co-primary показателя.','',
'## Достижение TP при SL=1σ72','',
'TP1/2/3 соответствуют q20/q50/q80. Ниже числа «достигнуто lower–upper / число строго положительных прогнозов», затем число нулевых прогнозов. Lower/upper отражают консервативную/оптимистическую границу MFE до стопа в минуте касания; это не результаты исполнения лестницы. Нулевые прогнозы не считаются успехами.','',
'| Arm / side | TP1 | TP2 | TP3 | Нулевые TP1/2/3 |','|---|---|---|---|---|']
for arm,m in r['metrics'].items():
    for si,side in enumerate(('long','short')):
        vals=[f"{m['TP_attained_lower'][si][1][k]}–{m['TP_attained_upper'][si][1][k]}/{m['TP_positive_denominators'][si][1][k]}" for k in range(3)]
        lines.append('| '+arm+' / '+side+' | '+' | '.join(vals)+' | '+ '/'.join(map(str,m['TP_zero_counts'][si][1]))+' |')
lines+=['','Более частое достижение меньшей дистанции само по себе не означает лучший прогноз; первичные proper losses выше учитывают величину прогноза. Все шесть side/SL строк и все 24 окна для каждого arm включены в CSV, без выбора удачных случаев.','',
'## Фиксированная display-лестница','',
'Правило задано заранее: argmax D определяет сторону; NONE или ничья → NO_TRADE. Выбирается минимальный SL с P(full72h adverse touch) ≤.25; отсутствие такого SL либо неположительные/нестрого возрастающие TP → NO_TRADE.','',
'| Arm | DISPLAY / NO_TRADE | TP1 lower–upper / n | TP2 | TP3 | Средняя touch p / наблюдаемая частота |','|---|---|---|---|---|---|']
for arm,m in r['metrics'].items():
    d=m['selected_display_ladder'];n=d['n'];vs=[]
    for k in range(3):vs.append(f"{round(d['TP_attained_lower_rates'][k]*n)}–{round(d['TP_attained_upper_rates'][k]*n)}/{n}" if n else '— (n=0)')
    touch=f"{d['predicted_full_horizon_adverse_touch']:.1%} / {round(d['observed_full_horizon_adverse_touch']*n)}/{n} ({d['observed_full_horizon_adverse_touch']:.1%})" if n else '—'
    lines.append(f"| {arm} | {n} / {d['NO_TRADE']} | "+' | '.join(vs)+f' | {touch} |')
lines+=['','P и C выбрали разные наборы случаев и разные дистанции; по частотам достижения этих выбранных лестниц нельзя сравнивать качество веток. Знаменатель каждого TP в выбранной лестнице — число DISPLAY; все выбранные TP строго положительны, нулевых прогнозов в этих лестницах нет. Безусловное касание adverse-барьера на полном H=72h не равно реализованному stopout после частичных TP. Лестницы описывают прогнозные дистанции, исполнения и финансовый результат не моделировались.','',
'## Пределы вывода и файлы','',
'FEASIBILITY_PASS означает достижение ≥90% валидного покрытия, а не наличие рыночного сигнала. Положительный сигнал требовал улучшения P против prior по обеим потерям, минимум 2/3 улучшенных folds и верхних границ первичных CI <0; добавочный эффект P−C проверяется отдельно тем же правилом. Эти требования не выполнены. Выборка 24 окна мала; 28d — только чувствительность к зависимости. Исторические данные могли присутствовать в pretraining; процедурная слепота и свежие контексты не доказывают отсутствие загрязнения. CHECK не открывался в этом опыте; прежняя экспозиция CHECK в других исследованиях остаётся ограничением.','',
'Финансовая оценка не проводилась. Нет оснований для утверждений о доходности, просадке, допуске к эксплуатации или торговом запуске. Исходные вторичные numeric/context/CNN controls не присоединялись: их variable-SL прогнозы не выдуманы.','',
'- `cases.csv`: 72 строки = 24 окна × P/C/prior, хронологически; потери, D, display.','- `forecast-details.csv`: 432 строки = 24 × 3 × 2 стороны × 3 SL; q20/50/80, truth lower/upper, touch p/truth, потери и числители/знаменатели TP.','- `summary.json`: компактные агрегаты и все первичные/чувствительные интервалы.','- `frozen/evaluation-results.json`: единственный исходный scoring, SHA256 `'+PIN+'`.','- `README_REPRODUCE.md`: проверка архивов и ограничения воспроизведения.','']
lines+=['## Покрытие квантилей и калибровка SL','',
'Покрытие квантиля здесь — доля Y ≤ q, а не доля достижения TP. При интервальной truth [lower,upper] гарантированное покрытие — upper ≤ q, возможное — lower ≤ q; включены все 24 случая, в том числе нулевые прогнозы. При атомах номинальный q не требует точного равенства наблюдаемой доли q: строгая и включающая равенство версии различаются. Полные counts обеих версий для всех 18 квантилей каждого arm сохранены в summary.json и построчно в CSV.','',
'| Arm / side / SL | q20: гарант.–возможн. / 24 | q50 | q80 |','|---|---|---|---|']
for row in summary['quantile_coverage_counts']:
    cc=row['counts']; vals=[f"{cc[k+'_quantile_coverage_upper_truth_inclusive']}–{cc[k+'_quantile_coverage_lower_truth_inclusive']}/24" for k in ('TP1','TP2','TP3')]
    lines.append('| '+row['arm']+' / '+row['side']+' / '+str(row['SL_sigma72'])+' | '+' | '.join(vals)+' |')
lines+=['','SL_calibration в summary.json содержит все шесть side/SL меню каждого arm, фиксированные bins [0,.2,.4,.6,.8,1], counts, среднюю прогнозную и наблюдаемую частоту; пустые bins имеют null. Это описательная калибровка малой выборки, без подгонки. Все меню оценены независимо от display.','',
'Проверка целостности при экспорте: SHA256 результата соответствует pin; freeze соответствует evaluation seal; все 58 сырых ответов соответствуют debug/evaluation seals; prompt/schema и 87 packet/chart файлов архива соответствуют freeze. Экспорт не вызывает scoring или модель.','']
(BASE/'REPORT.md').write_text('\n'.join(lines))
readme = f"""# Воспроизведение экспорта и границы повторного scoring

Этот каталог хранит завершённое ограниченное сравнение. Экспорт читает только frozen result, freeze, seals, сырые ответы и архив; новые прогнозы, обучение, рыночные данные и scoring не запускаются.

Из корня worktree:

```sh
/Users/vf/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 reports/btc-pattern-pilot-m2-20261021/inapp-chatgpt-protocol-20261022/export_report.py
```

Достаточен Python 3 standard library. Экспорт заново создаёт REPORT.md, summary.json, cases.csv и forecast-details.csv и этот README; frozen/evaluation-results.json не изменяется. CSV содержат 72 и 432 строки данных соответственно, плюс заголовок. Строки упорядочены по origin, затем P/C/prior, long/short, SL=.75/1/1.5.

Проверки перед экспортом: result SHA256={PIN}; freeze SHA256={sha(BASE/'frozen/freeze.json')} совпадает с evaluation seal; 10 debug и 48 evaluation сырых ответов проверяются по SHA256 из seals; prompt/schema и все 87 packet/chart файлов в архиве также соответствуют freeze. Итог PASS и SHA256 архива отражены в summary.json. Проверки используют исключения assert, поэтому не запускать Python с -O.

Архив входов frozen-input-packets.tar.gz имеет SHA256={sha(BASE/'frozen-input-packets.tar.gz')}. Он сохраняет исходные packet.json и chart.png; сырые ответы отдельно находятся в raw-responses/. Freeze содержит хеши пакетов, prompt/schema, source и шести prepared-массивов. Исходный freeze закреплён до раскрытия truth; статус READY в нём исторический, итоговый статус находится в evaluation-results.json. PROTOCOL_PROPOSAL.md также сохраняет исходную формулировку предложения, а не текущий статус завершённого опыта.

Повторный scoring — отдельная операция, здесь она не выполнялась. Для него нужен исходный закреплённый prepared-набор, включая metadata.npy и minutes.npy, а для полной проверки происхождения — все шесть массивов из source_hashes, исходный manifest (SHA256 bc660056af9117a246a1334837b7e42c9bb2d0635945a0346a4b088a459685ff), source и зависимости с точными версиями. Архив packet/chart и ответы сами по себе не содержат все будущие минутные пути и не заменяют prepared. Предыдущий bootstrap seed=7 не фиксирует генерацию языковой модели; backend snapshot, sampling seed и temperature не закреплены интерфейсом. Повторный вызов forecaster не является точным воспроизведением.

Для отдельного разрешённого повторного scoring следует создать свежий scratch-каталог с копиями freeze/seal и ответов, проверить исходные SHA256 и prepared source_hashes, восстановить пути prepared и response_path в производных копиях и пересчитать freeze_sha256 в производной seal. Исходные файлы и их хеши сохраняются; изменения путей документируются как relocation, не новый запуск. У scratch-копии не должно быть evaluation-results.json: scorer намеренно отвергает существующий результат с RESULT_ALREADY_EXISTS. Из worktree root с PYTHONPATH=runtime вызывается модуль coinmaster.research.btc_pattern_inapp, команда score-after-seal --freeze <scratch/freeze.json>. Нельзя запускать эту команду на оригинальном freeze и нельзя удалять/перезаписывать исходный результат. Сравниваются числовые поля и cases производного результата с закреплённым результатом; абсолютные пути receipt могут различаться. Для повторного bootstrap требуется NumPy; версии среды должны быть записаны отдельно.

Текущий отчёт — экспорт единственного уже выполненного scoring. FEASIBILITY_PASS означает валидный формат/покрытие; exploratory_signal=false и window_bundle_incremental=false. Финансовой оценки, будущего запуска и допуска к эксплуатации этот каталог не предоставляет.
"""
(BASE/'README_REPRODUCE.md').write_text(readme)
print(json.dumps({'rows':{'cases':len(case_rows),'forecast_details':len(detail_rows)},'status':r['status'],'metrics':{a:{'scores':m['all_ID'],'D_accuracy':m['D_accuracy']} for a,m in r['metrics'].items()}}))
