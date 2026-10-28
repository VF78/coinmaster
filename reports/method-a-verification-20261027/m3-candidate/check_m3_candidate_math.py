"""Single analytical DATA bound and exact chosen-tick conditional proof; native0."""
from pathlib import Path
helper=Path("reports/method-a-verification-20261027/m3-feasibility/check_corrected_planning.py")
exec(helper.read_text().split('cash=D(')[0])
from coinmaster.strategy.method_a_risk import useful_hedge
rr=[Observation(int(b.close_time.timestamp()*10**9),max(int(b.available_at.timestamp()*10**9),int(b.close_time.timestamp()*10**9)+MINUTE),D(str(b.btc_close)),D(str(b.sol_close)))for b in seed()[:730]]
f=lagged_features(rr,[Funding(a,b,c,D(d),e)for a,b,c,d,e in funding()],100804*10**9)
L=D("7.875");half=L/2;mark=D("100.3");c=TAKER+RESERVE
ec=1-half*TAKER-half*(mark/100-1)
rc=L*mark/100*(f.b+(1+f.b)*c)+half*mark/100*c
Bmin=5000/(ec-rc);slope=D("132.7")*(1+TAKER)
closemax=130-(Bmin-D("5746.38445250"))/slope
P=D(128);B=D("5746.38445250")+slope*(130-P)
Q=(B*L/100/D(".001")).to_integral_value(rounding="ROUND_FLOOR")*D(".001")
Fq=(Q/D(".001")//2)*D(".001");Sq=Q-Fq
st=State(-Fq,D(0),B-Fq*100*TAKER+Fq*(100-mark),D(10000),mark,D(100))
li=[Liability("SECOND","BTC",-1,int(Sq/D(".001")),D(".001"),False,mark*c),Liability("BTC_TPS","BTC",1,int(Fq/D(".001")),D(".001"),True,mark*c)]
second=tier_partition_envelope(st,f,li,margin,bounds);assert second.safe
cash=B-Fq*100*TAKER-Sq*mark*D(".00020");notional=Fq*100+Sq*mark
k=f.b+(1+f.b)*c
price_for_u=lambda u:u*(cash+notional-5000)/(Q*(k+u))
PB=D("99.9");ss=State(-Q,D(0),cash+notional-Q*PB,D(10000),PB,D(100))
on,band,t=hedge_target(ss,f,False,True);t=(t/D(".1")).to_integral_value(rounding="ROUND_FLOOR")*D(".1")
ll=[Liability("BTC_TPS","BTC",1,int(Q/D(".001")),D(".001"),True,PB*c),Liability("SOL_ENTRY","SOL",1,int(t/D(".1")),D(".1"),False,D(100)*c)]
entry=tier_partition_envelope(ss,f,ll,margin,bounds)
assert on and band=="MEDIUM" and entry.safe and useful_hedge(ss,f,t)[0] and t==D("196.4")
stopstate=State(-Q,t-D(".1"),ss.equity-t*100*TAKER-t*2-D(".1")*98*TAKER,D(10000),PB,D(98))
stop=evaluate(stopstate,f,margin);assert stop.worst_deficit<0 and stop.margin_pass
assert not calls
payload=dict(status="CONDITIONAL_PLANNING_MATH_ONLY_NOT_NATIVE_PNL",base_source=source,formula=dict(Q="7.875*B/100 before exact native lot floor",FIRST="floor(parentlots/2)*.001",FIRST_equity_coefficient=str(ec),pending_SECOND_loss_coefficient=str(rc),B_min="5000/(FIRST_equity_coefficient-pending_SECOND_loss_coefficient)",flatcapital="5746.38445250+132.772985*(130-closeprice)",why_extremum="Same-side native BTC exposure only: positive loss slope dominates paid reductioncost; maximum at full original inventory. Actual filled VWAP/fees checked by exact native-lot point."),B_min=str(Bmin),closeprice_upper_bound=str(closemax),chosen_OFF_CLOSE=str(P),hypothetical_first_parent_flatcapital=str(B),continuous_peak_lower_bound="10000; any larger actualH must fail the case cash/peak assertion",original_parent=str(Q),FIRST=str(Fq),SECOND=str(Sq),own_filled_VWAP=str(notional/Q),after_both_entry_BASEfees_cash=str(cash),SECOND_contemporaneous_state=asdict(st),SECOND_envelope=asdict(second),MEDIUM_interval=[str(price_for_u(D(".70"))),str(price_for_u(D(".85")))],selected_contemporaneous_PB=str(PB),selection_state=asdict(ss),target=str(t),entry_envelope=asdict(entry),partial_STOP_state=asdict(stopstate),partial_STOP_current_evaluation=asdict(stop),rejected130_alternative=dict(flatB="5746.38445250",SECOND_cross100_3_worst_deficit="151.91551245786662611680498142521212173000000000000000000000000",classification="DATA_PROPOSAL_REJECTED_NOT_PRODUCT_FAILURE"),native_constructors=0,actual_money_claim=False,helper_sha256=sha(helper))
def wire(v):
 if isinstance(v,D):return str(v)
 if isinstance(v,dict):return {str(k):wire(x)for k,x in v.items()}
 if isinstance(v,(tuple,list)):return [wire(x)for x in v]
 return v
out=p/"m3-candidate"/"M3_ANALYTIC_BOUND.json"
out.write_text(json.dumps(wire(payload),sort_keys=True,indent=2)+"\n")
print("B_min",Bmin,"P_max",closemax,"P",P,"B",B,"native0")
