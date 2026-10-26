"""Plot saved native report metrics with ReportLab; no economic engine."""
from pathlib import Path
from decimal import Decimal as D
import csv, json
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Circle
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics import renderSVG
from reportlab.lib import colors
P=Path(__file__).resolve().parent
ROWS=[('S0', '6077107.23887483', '66.256914864686864', 'legacy'), ('E4', '5631617.35953723', '57.58541045962226', 'legacy'), ('C1', '4388613.38225343', '51.80315157406655', 'legacy'), ('B25', '2394463.52298288', '46.48498', 'legacy'), ('B', '4622034.27336437', '57.58541045962226', 'legacy'), ('M1', '2615745.21476479', '58.77409504467890', 'legacy'), ('M2', '2044863.63091774', '70.64462755333228', 'legacy'), ('R1', '304372.03028516', '66.9203964274', 'legacy_TP_SOLoff'), ('R2', '225919.51131228', '66.8014965826', 'real3TP_SOLoff'), ('R3', '120718.40416503', '68.6033754263', 'real3TP_SOLoff')]
base=D(ROWS[0][1])-D(10000)
data=[dict(label=n,total=t,reported_DD_pct=dd,legacy_S0_net_retention_pct=str((D(t)-D(10000))/base*100),contract=c)for n,t,dd,c in ROWS]
with(P/'full_period_frontier.csv').open('w')as f:
 w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
d=Drawing(1100,640);d.add(Rect(0,0,1100,640,fillColor=colors.HexColor('#fafcfc'),strokeColor=None))
X,Y,W,H=100,120,900,400
xx=lambda v:X+W*v/110
yy=lambda v:Y+H*(v-30)/47
d.add(Rect(xx(70),Y,xx(110)-xx(70),yy(50)-Y,fillColor=colors.HexColor('#e8f3e8'),strokeColor=None));d.add(Rect(xx(90),Y,xx(110)-xx(90),yy(50)-Y,fillColor=colors.HexColor('#cfe5d1'),strokeColor=None))
chart=LinePlot();chart.x=X;chart.y=Y;chart.width=W;chart.height=H;chart.data=[[(0,30),(110,77)]];chart.lines[0].strokeColor=None;chart.lines[0].symbol=None
chart.xValueAxis.valueMin=0;chart.xValueAxis.valueMax=110;chart.xValueAxis.valueSteps=list(range(0,111,10));chart.yValueAxis.valueMin=30;chart.yValueAxis.valueMax=77;chart.yValueAxis.valueSteps=list(range(30,76,5));chart.xValueAxis.labels.fontSize=10;chart.yValueAxis.labels.fontSize=10;d.add(chart)
for v in range(35,76,5):d.add(Line(X,yy(v),X+W,yy(v),strokeColor=colors.HexColor('#dde3e6'),strokeWidth=.4))
d.add(Line(X,yy(50),X+W,yy(50),strokeColor=colors.HexColor('#438552'),strokeWidth=1,strokeDashArray=[5,4]))
for v in (70,90):d.add(Line(xx(v),Y,xx(v),Y+H,strokeColor=colors.HexColor('#7c9b83'),strokeWidth=.7,strokeDashArray=[3,4]))
off={'S0':(-26,14),'E4':(10,10),'C1':(10,12),'B25':(10,-18),'B':(-19,13),'M1':(-7,-18),'M2':(9,8),'R1':(16,-34),'R2':(16,-16),'R3':(16,9)}
for r in data:
 x=xx(float(r['legacy_S0_net_retention_pct']));y=yy(float(r['reported_DD_pct']));c=colors.HexColor('#a36c28'if r['contract'].startswith('legacy')else'#267a9f');d.add(Circle(x,y,5,strokeColor=c,strokeWidth=1.8,fillColor=None if r['contract'].startswith('legacy')else c));dx,dy=off[r['label']];d.add(String(x+dx,y+dy,r['label'],fontSize=11,fillColor=c))
d.add(String(100,605,'CoinMaster full-period research: profit retained vs drawdown',fontName='Helvetica-Bold',fontSize=19));d.add(String(100,580,'No point qualifies as a strategy with current real-TP / true-SOL-hedge requirements.',fontSize=11,fillColor=colors.HexColor('#5b6169')))
d.add(String(120,540,'Hollow: legacy TP (SOL variants)',fontSize=10,fillColor=colors.HexColor('#a36c28')));d.add(String(420,540,'Solid: real 3TP, SOL off',fontSize=10,fillColor=colors.HexColor('#267a9f')))
d.add(String(xx(72),yy(35),'Intermediate: >=70% profit / DD<=50%',fontSize=10,fillColor=colors.HexColor('#476c50')));d.add(String(xx(91),yy(43),'Final: >=90%',fontSize=10,fillColor=colors.HexColor('#2d6038')))
d.add(String(100,560,'Reported marked minute / settled max DD (%)',fontSize=10));d.add(String(350,75,'Net profit retained relative to original S0 (%)',fontSize=12));d.add(String(100,38,'2024-09-01..2026-09-01; seed10,000 USDT. Different historical execution contracts, diagnostic research only.',fontSize=10,fillColor=colors.HexColor('#626a70')));d.add(String(100,20,'Reported DD is not an intraminute bound or current coherent-event/venue qualification. See REVIEW_RU.md.',fontSize=10,fillColor=colors.HexColor('#626a70')))
renderSVG.drawToFile(d,str(P/'full_period_frontier.svg'))
try:
 import fitz
 doc=fitz.open(P/'full_period_frontier.svg');doc[0].get_pixmap(matrix=fitz.Matrix(1.7,1.7)).save(P/'full_period_frontier.png');doc.close();png=True
except ImportError:png=False
print(json.dumps({'saved_rows':len(data),'new_economic_runs':0,'svg':True,'png':png}))
