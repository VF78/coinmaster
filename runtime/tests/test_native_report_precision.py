from decimal import Decimal as D,localcontext,getcontext
import copy,json
import pytest
from coinmaster.research.native_baseline import assert_report_boundaries

REPORT=json.loads('{"run_interval":{"end_exclusive":"2026-09-01T00:00:00+00:00","initial_active_seed":"10000","start":"2024-09-01T00:00:00+00:00"},"summary":{"monthly_returns":[{"month":"2024-09","return":"0.173330144133","total":"11733.30144133"},{"month":"2024-10","return":"1.290009886376386052442491970","total":"26869.37630048"},{"month":"2024-11","return":"1.608089488083432626819847409","total":"70077.73788064"},{"month":"2024-12","return":"0.132828874790799533156019281","total":"79386.08495121"},{"month":"2025-01","return":"1.308932702728983631906613248","total":"183297.12768547"},{"month":"2025-02","return":"0.336063170941183263690472946","total":"244896.54163986"},{"month":"2025-03","return":"0.758766035967351471190973202","total":"430715.71976205"},{"month":"2025-04","return":"-0.0830212963708520261843339259","total":"394957.14234010"},{"month":"2025-05","return":"0.021004194516215314939247690","total":"403252.89898338"},{"month":"2025-06","return":"-0.0332097906878580102191210785","total":"389860.95461387"},{"month":"2025-07","return":"0.126038033510965636144786956","total":"438998.26267611"},{"month":"2025-08","return":"0.582521321531772964739329608","total":"694724.11080035"},{"month":"2025-09","return":"0.549132101899777340741079513","total":"1076219.42200460"},{"month":"2025-10","return":"0.268800979297308681626108379","total":"1365508.25657822"},{"month":"2025-11","return":"0.224807038826319680640470206","total":"1672484.12423246"},{"month":"2025-12","return":"0.137682403004313569554467871","total":"1902755.75744335"},{"month":"2026-01","return":"0.102966577572672543401562615","total":"2098676.00574399"},{"month":"2026-02","return":"0.520357732776002768656032592","total":"3190738.29392433"},{"month":"2026-03","return":"0.545109957187779459564915126","total":"4930041.50872283"},{"month":"2026-04","return":"0.413172941094904104606246748","total":"6967001.25860180"},{"month":"2026-05","return":"-0.0432304387200548316562785673","total":"6665814.73762927"},{"month":"2026-06","return":"0.071795796435374447337736131","total":"7144392.21560802"},{"month":"2026-07","return":"-0.3151638724393750353863251881","total":"4892737.89871127"},{"month":"2026-08","return":"-0.1682836976326429113748594420","total":"4069369.87356877"}],"interval_cash_terminal_total":"4069369.87356877","drawdown_start":"2026-05-03 20:37:00+00:00","drawdown_trough":"2026-08-19 08:00:00+00:00"},"fill_timestamps_ns":[],"post_boundary_settlement":{"convention":"TERMINAL_FILLS_AT_END_EXCLUSIVE_REPORTED_SEPARATELY_EXCLUDED_FROM_INTERVAL_RETURNS","fill_count":0}}')

def test_native_24month_compounding_avoids_context28_false_rejection():
    report=copy.deepcopy(REPORT)
    with localcontext() as ctx:
        ctx.prec=28
        compound=D(1)
        for row in report['summary']['monthly_returns']:compound*=1+D(row['return'])
        ratio=D(report['summary']['interval_cash_terminal_total'])/D(report['run_interval']['initial_active_seed'])
        assert abs(compound-ratio)==D('1.2e-24')
    before=copy.deepcopy(report);precision=getcontext().prec
    assert_report_boundaries(report)
    assert report==before and getcontext().prec==precision

def test_compounding_precision_keeps_original_threshold_and_detects_real_error():
    report=copy.deepcopy(REPORT)
    report['summary']['monthly_returns'][-1]['return']=str(D(report['summary']['monthly_returns'][-1]['return'])+D('.00001'))
    with pytest.raises(ValueError,match='MONTHLY_COMPOUNDING_MISMATCH'):
        assert_report_boundaries(report)
