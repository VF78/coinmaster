"""Synthetic native records only; no runtime/engine/account imports."""
import copy
import unittest
from decimal import Decimal as D
import native_attribution as tool

BTC='BTC-USD-PERP.HYPERLIQUID';SOL='SOL-USD-PERP.HYPERLIQUID';H=tool.STEP


def fixture(retrospective=False):
    rows=[]
    def state(kind,event,epoch,cash,positions,identity=None,delta=None,state_epoch=None,receipt=None,retention=None):
        signature='0'*64 if not positions else '1'*64 if len(positions)==1 else '2'*64
        row=dict(sequence=len(rows)+1,kind=kind,event_ns=str(event),receipt_ns=str(event if receipt is None else receipt),
            epoch=epoch,state_epoch=epoch if state_epoch is None else state_epoch,cash=str(cash),
            equity=str(D(cash)+sum((D(p['native_upnl']) for p in positions),D(0))),positions=copy.deepcopy(positions),
            native_positions_sha256=signature,mark_available_ns=str(event),native_id=identity)
        if delta is not None:row['native_cash_delta']=str(delta)
        if retention is not None:row['prior_source_retention']=retention
        rows.append(row);return row
    def pos(i,upnl,side):return dict(instrument_id=i,quantity='1',side=side,native_upnl=str(upnl))
    b=[pos(BTC,0,'LONG')];both=b+[pos(SOL,0,'SHORT')]
    state('PREQUOTE_DIRECT_NATIVE',0,0,10000,[])
    state('PRE_FILL_LAST_COMMITTED_NATIVE_COPY',1,0,10000,[],'B')
    state('POST_FILL_COMMITTED_NATIVE',1,1,9998,b,'B',-2)
    state('PRE_FILL_LAST_COMMITTED_NATIVE_COPY',2,1,9998,b,'S')
    state('POST_FILL_COMMITTED_NATIVE',2,2,9997,both,'S',-1)
    state('PRE_FUNDING_COMMITTED_NATIVE_COPY',3,2,9997,both,'FS')
    state('POST_FUNDING_ACCOUNT_NATIVE',3,3,10000,both,'FS',3)
    marked=[pos(BTC,-10,'LONG'),pos(SOL,4,'SHORT')]
    if retrospective:
        state('PRE_FUNDING_COMMITTED_NATIVE_COPY',H+1,3,10000,marked,'FB')
        state('POST_FUNDING_ACCOUNT_NATIVE',H+1,4,9995,marked,'FB',-5)
        state(tool.WM,H,4,10000,marked,state_epoch=3,receipt=H+1,
            retention=dict(source_ns=str(H),state_epoch=3,signature=['10000','2'*64],first_new_mutation_ns=str(H+1)))
    else:state(tool.WM,H,3,10000,marked,receipt=H+1)
    count=4 if retrospective else 3
    report={'fill_audit':[{'trade_id':'B','instrument':BTC,'fill_ns':'1','commission':'2'},
        {'trade_id':'S','instrument':SOL,'fill_ns':'2','commission':'1'}],
        'funding_cash_audit':[['FS',SOL,3,'9997','10000','3']],
        'coherent_native_observer':{'status':'PASS','unknown':[],'sequence_count':len(rows),'native_unique_fills':2,'native_funding_transitions':count-2}}
    if retrospective:report['funding_cash_audit'].append(['FB',BTC,H+1,'10000','9995','-5'])
    return report,rows


def terminal_fixture():
    """Two actually mapped close records, then native flat cash at exact end."""
    report,rows=fixture()
    both=copy.deepcopy(rows[-1]['positions']);sol=[copy.deepcopy(both[1])]
    def add(kind,event,epoch,cash,positions,identity=None,delta=None):
        signature='0'*64 if not positions else '1'*64 if len(positions)==1 else '2'*64
        row=dict(sequence=len(rows)+1,kind=kind,event_ns=str(event),receipt_ns=str(event),
            epoch=epoch,state_epoch=epoch,cash=str(cash),
            equity=str(D(cash)+sum((D(p['native_upnl']) for p in positions),D(0))),
            positions=copy.deepcopy(positions),native_positions_sha256=signature,
            mark_available_ns=str(event),native_id=identity)
        if delta is not None:row['native_cash_delta']=str(delta)
        rows.append(row)
    add('PRE_FILL_LAST_COMMITTED_NATIVE_COPY',H+2,3,10000,both,'BC')
    add('POST_FILL_COMMITTED_NATIVE',H+2,4,9989,sol,'BC',-11)
    add('PRE_FILL_LAST_COMMITTED_NATIVE_COPY',H+3,4,9989,sol,'SC')
    add('POST_FILL_COMMITTED_NATIVE',H+3,5,9992,[],'SC',3)
    add('DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED',2*H,5,9992,[])
    report['fill_audit'] += [{'trade_id':'BC','instrument':BTC,'fill_ns':str(H+2),'commission':'1'},
                            {'trade_id':'SC','instrument':SOL,'fill_ns':str(H+3),'commission':'1'}]
    report['coherent_native_observer'].update(sequence_count=len(rows),native_unique_fills=4)
    return report,rows


class AttributionTests(unittest.TestCase):
    def test_actual_fee_funding_cash_plus_native_upnl_reconciles_once(self):
        report,rows=fixture();windows,result=tool.attribute(report,rows,0,H)
        self.assertEqual(result['global_unknown_reasons'],[])
        w=windows[0];self.assertEqual(w['status'],'NATIVE_ATTRIBUTION_RECONCILED')
        self.assertEqual((D(w['BTC_pnl']),D(w['SOL_pnl']),D(w['native_joint_pnl'])),(D(-12),D(6),D(-6)))
        self.assertEqual(D(w['BTC_cash_delta']),-2);self.assertEqual(D(w['SOL_cash_delta']),2)
        self.assertEqual(D(w['asset_sum_minus_native_equity_delta']),0)
        diagnostics=result['conditional_diagnostics']
        self.assertEqual(diagnostics['BTC_adverse']['SOL_positive_contribution_sum'],'6')
        self.assertEqual(diagnostics['BTC_ranked_worst5pct_matched_windows']['joint_mean'],'-6')
    def test_retrospective_watermark_uses_state_epoch_not_newer_funding_cash(self):
        report,rows=fixture(True);windows,result=tool.attribute(report,rows,0,H)
        self.assertEqual(result['global_unknown_reasons'],[])
        self.assertEqual(windows[0]['end_state_epoch'],3)
        self.assertEqual(D(windows[0]['BTC_cash_delta']),-2) # not latest epoch's -7
        self.assertEqual(D(windows[0]['native_joint_pnl']),-6)
        bad=copy.deepcopy(rows);del bad[-1]['prior_source_retention']
        windows,result=tool.attribute(report,bad,0,H)
        self.assertEqual(windows[0]['status'],'UNKNOWN');self.assertIsNone(windows[0]['BTC_pnl'])
    def test_unmapped_duplicate_foreign_and_sequence_gap_never_become_zero(self):
        for corruption in ('unmapped','duplicate','foreign','gap'):
            with self.subTest(corruption=corruption):
                report,rows=fixture()
                if corruption=='unmapped':report['fill_audit']=report['fill_audit'][1:]
                if corruption=='duplicate':report['fill_audit'].append(copy.deepcopy(report['fill_audit'][0]))
                if corruption=='foreign':rows[-1]['positions'][0]['instrument_id']='ETH-USD-PERP.HYPERLIQUID'
                if corruption=='gap':rows[4]['sequence']+=1
                windows,result=tool.attribute(report,rows,0,H)
                self.assertTrue(result['global_unknown_reasons']);self.assertEqual(windows[0]['status'],'UNKNOWN')
                self.assertIsNone(windows[0]['BTC_pnl']);self.assertIsNone(windows[0]['SOL_pnl'])
    def test_missing_boundary_retains_unknown_window_and_known_population(self):
        report,rows=fixture();windows,result=tool.attribute(report,rows,0,2*H)
        self.assertEqual(len(windows),2)
        self.assertEqual(windows[0]['status'],'NATIVE_ATTRIBUTION_RECONCILED')
        self.assertEqual(windows[1]['status'],'UNKNOWN');self.assertIsNone(windows[1]['SOL_pnl'])
        self.assertEqual(result['conditional_diagnostics']['known_windows'],1)
        self.assertEqual(result['conditional_diagnostics']['unknown_windows'],1)
        self.assertIn('UNKNOWN',result['terminal_native_flat_cash_separate']['status'])
    def test_ambiguous_zero_funding_identity_is_unknown(self):
        report,rows=fixture()
        report['funding_cash_audit']=[['ZERO',BTC,3,'9997','9997','0'],['ZERO',SOL,3,'9997','9997','0']]
        rows[-3]['native_id']='ZERO';rows[-2].update(native_id='ZERO',cash='9997',equity='9997',native_cash_delta='0')
        report['coherent_native_observer']['native_funding_transitions']=2
        windows,result=tool.attribute(report,rows,0,H)
        self.assertIn('AMBIGUOUS_OR_UNMAPPED_NATIVE_FUNDING_MONEY',result['global_unknown_reasons'])
        self.assertEqual(windows[0]['status'],'UNKNOWN');self.assertIsNone(windows[0]['SOL_cash_delta'])

    def test_valid_terminal_allocation_reconciles_and_labels_direct_cash(self):
        report,rows=terminal_fixture();_,result=tool.attribute(report,rows,0,2*H)
        self.assertEqual(result['global_unknown_reasons'],[])
        terminal=result['terminal_native_flat_cash_separate']
        self.assertEqual(terminal['status'],'NATIVE_FLAT_CASH_RECONCILED')
        self.assertEqual(terminal['asset_cash_delta'],{'BTC':'-13','SOL':'5'})
        self.assertEqual(terminal['native_asset_cash_sum'],'-8')
        self.assertEqual(terminal['native_cash_minus_seed'],'-8')
        observed=terminal['direct_native_flat_cash_observation']
        self.assertEqual(observed['status'],'DIRECT_NATIVE_FLAT_ROW_OBSERVATION_ONLY')
        self.assertEqual(observed['cash'],'9992')
    def test_terminal_gap_upstream_unknown_or_coverage_cannot_certify_allocation(self):
        for corruption in ('terminal_gap','upstream_unknown','missing_coverage'):
            with self.subTest(corruption=corruption):
                report,rows=terminal_fixture()
                if corruption=='terminal_gap':
                    rows[-1]['sequence']+=1
                    report['coherent_native_observer']['sequence_count']=rows[-1]['sequence']
                elif corruption=='upstream_unknown':
                    report['coherent_native_observer'].update(status='UNKNOWN',unknown=['SYNTHETIC_COVERAGE_UNKNOWN'])
                else:
                    report['fill_audit'].append({'trade_id':'UNOBSERVED','instrument':BTC,'fill_ns':'4'})
                _,result=tool.attribute(report,rows,0,2*H)
                self.assertTrue(result['global_unknown_reasons'])
                terminal=result['terminal_native_flat_cash_separate']
                self.assertEqual(terminal['status'],'UNKNOWN_NATIVE_ASSET_ATTRIBUTION')
                self.assertEqual(terminal['unknown_reasons'],result['global_unknown_reasons'])
                self.assertIsNone(terminal['asset_cash_delta'])
                self.assertIsNone(terminal['native_asset_cash_sum'])
                self.assertIsNone(terminal['native_cash_minus_seed'])
                self.assertEqual(terminal['direct_native_flat_cash_observation']['cash'],'9992')
                self.assertEqual(terminal['direct_native_flat_cash_observation']['status'],'DIRECT_NATIVE_FLAT_ROW_OBSERVATION_ONLY')


if __name__=='__main__':unittest.main()
