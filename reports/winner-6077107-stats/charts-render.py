#!/usr/bin/env python3
"""Reproduce static charts using installed ReportLab standard plotting (no dependency install).
Input charts-input.json holds only verified reduced report series. Plotting never runs an engine.
Run python3 charts-render.py; optional SVG rasterization uses installed Node/sharp separately.
"""
import json,math,pathlib,datetime
from reportlab.graphics.shapes import Drawing,String,Rect,Circle,Line
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics import renderSVG
from reportlab.lib import colors
R=pathlib.Path(__file__).resolve().parent; D=json.loads((R/'charts-input.json').read_text())
C=lambda c:colors.HexColor(c)
INK=C('#172438'); MUT=C('#596b80'); BLUE=C('#1765a5'); RED=C('#c64646'); GREEN=C('#16866c'); GRID=C('#dce3ec')
def text(g,x,y,s,size=20,color=INK,anchor='start',bold=False):g.add(String(x,y,str(s),fontName='Helvetica-Bold' if bold else 'Helvetica',fontSize=size,fillColor=color,textAnchor=anchor))
def base(h,title,sub):
 g=Drawing(1500,h);g.add(Rect(0,0,1500,h,fillColor=C('#f6f8fc'),strokeColor=None));text(g,65,h-57,title,32,bold=True);text(g,65,h-95,sub,20,MUT);return g
def plot(g,data,y,h,vmin,vmax,steps,fmt,color):
 p=LinePlot();p.x=125;p.y=y;p.width=1310;p.height=h;p.data=[data];p.joinedLines=1;p.lines[0].strokeColor=color;p.lines[0].strokeWidth=2.2
 p.xValueAxis.valueMin=0;p.xValueAxis.valueMax=max(i for i,v in data);p.xValueAxis.strokeColor=MUT;p.xValueAxis.labels.fontSize=16;p.xValueAxis.labels.fillColor=MUT
 p.yValueAxis.valueMin=vmin;p.yValueAxis.valueMax=vmax;p.yValueAxis.valueSteps=steps;p.yValueAxis.labelTextFormat=fmt;p.yValueAxis.strokeColor=MUT;p.yValueAxis.labels.fontSize=17;p.yValueAxis.labels.fillColor=MUT;p.yValueAxis.visibleGrid=True;p.yValueAxis.gridStrokeColor=GRID;p.yValueAxis.gridStrokeWidth=.7
 g.add(p);return p
rows=D['daily'];n=len(rows);g=base(1040,'Winner 6,077,107.24 USDT',D['period_label']+'  |  Native marked portfolio equity')
text(g,65,897,'Equity growth',23,bold=True);text(g,1435,897,'USDT | logarithmic scale',18,MUT,anchor='end')
vals=[r['equity_usdt'] for r in rows];lo=math.floor(math.log10(min(vals)));hi=math.ceil(math.log10(max(vals)))
p=plot(g,[(i,math.log10(r['equity_usdt'])) for i,r in enumerate(rows)],550,300,lo,hi,list(range(lo,hi+1)),lambda v:f'{10**v:,.0f}',BLUE)
p.xValueAxis.visible=False
text(g,125,510,f'Start: {D["initial_equity_usdt"]:,.2f} USDT',19,MUT);text(g,1435,510,f'Last mark: {D["final_equity_usdt"]:,.2f} USDT',19,BLUE,'end',True)
text(g,65,451,'Portfolio drawdown from running peak',23,bold=True);text(g,1435,451,'Daily close sample (%)',18,MUT,'end')
p=plot(g,[(i,-r['close_drawdown_pct']) for i,r in enumerate(rows)],205,200,-80,0,[-80,-60,-40,-20,0],lambda v:f'{v:g}%',RED)
ticks=sorted(set([0,n-1]+[round((n-1)*j/6) for j in range(1,6)]));p.xValueAxis.valueSteps=ticks;p.xValueAxis.labelTextFormat=lambda v:rows[min(n-1,max(0,round(v)))]['date'][:10]
trough=datetime.datetime.fromisoformat(D['native_max_drawdown_time'].replace(' UTC','')).date();first=datetime.date.fromisoformat(rows[0]['date']);tx=125+1310*(trough-first).days/(n-1);ty=205+200*(1-D['native_max_drawdown_pct']/80)
g.add(Circle(tx,ty,5,fillColor=RED,strokeColor=None));text(g,tx+15,ty-6,'Full native trough',17,RED)
text(g,1435,139,f'Full native maximum: {D["native_max_drawdown_pct"]:.5f}% | trough {D["native_max_drawdown_time"]}',23,RED,'end',True)
text(g,65,99,D['equity_note'],17,MUT);text(g,65,69,D['funding_note'],17,MUT);text(g,65,39,'Source: verified existing native run; no new backtest. All dates UTC.',16,MUT)
renderSVG.drawToFile(g,str(R/'charts-equity-drawdown.svg'))
# Calendar heatmap avoids a compressed bar axis when month returns differ greatly.
months=D['monthly'];years=sorted(set(int(r['month'][:4]) for r in months));H=390+len(years)*135
g=base(H,'Monthly native equity returns',D['period_label']+'  |  Relative to prior month-end equity')
startx=180;cellw=101;top=H-175
for m,s in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']):text(g,startx+m*cellw+47,top+25,s,19,MUT,'middle')
lookup={r['month']:r for r in months}
for yi,year in enumerate(years):
 y=top-yi*135-110;text(g,150,y+49,year,22,anchor='end',bold=True)
 for m in range(1,13):
  r=lookup.get(f'{year}-{m:02d}');xx=startx+(m-1)*cellw
  if r is None:
   g.add(Rect(xx,y,95,110,rx=9,ry=9,fillColor=C('#e8edf3'),strokeColor=None));text(g,xx+47,y+49,'-',21,MUT,'middle');continue
  v=r['return_pct'];c=GREEN if v>=0 else RED;alpha=.15+.70*min(abs(v)/100,1);mixed=colors.Color(*(1-alpha+alpha*t for t in (c.red,c.green,c.blue)))
  g.add(Rect(xx,y,95,110,rx=9,ry=9,fillColor=mixed,strokeColor=None));text(g,xx+47,y+54,f'{v:+.1f}%',19,anchor='middle',bold=True)
  if r.get('terminal_settlement'):text(g,xx+47,y+25,'FINAL*',13,anchor='middle')
text(g,65,159,D['monthly_note'],18,MUT);text(g,65,124,D['funding_note'],17,MUT);text(g,65,89,'Green = positive; red = negative. Color saturation caps at |100%|; figures are uncapped.',17,MUT);text(g,65,54,'Source: verified existing native run; no new backtest. All dates UTC.',16,MUT)
renderSVG.drawToFile(g,str(R/'charts-monthly-returns.svg'))
