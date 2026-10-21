from pathlib import Path
import hashlib,json,sys
from coinmaster.research.forecast_independent_data import Dataset
from coinmaster.research.forecast_independent_models import render
repo=Path.cwd();r=repo/'reports/forecast-independent-20261021';prepared=Path(json.loads((r/'prepare-launch.json').read_text())['job'])/'result/prepared-v1';ds=Dataset(prepared,r/'protocol.json');images=[]
for row in [0,1]:
 x,_=ds.features([row],'60x20');image=render(x[0]);images.append({'row':row,'view':'60x20','dtype':str(image.dtype),'shape':list(image.shape),'sha256':hashlib.sha256(image.tobytes()).hexdigest(),'origin_ms':int(ds.meta['origin'][row])})
base=Path('/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-pred02-profile-cnn-20261021T111804Z/result/profile')
files=[{'source':str(base/name),'relative':'VPS-CNN20-'+name,'sha256':hashlib.sha256((base/name).read_bytes()).hexdigest(),'bytes':(base/name).stat().st_size} for name in ['profile-predictions.npz','result.json']]
out={'status':'TRAIN_ONLY_RENDER_BASELINE','images':images,'files':files,'CHECK_opened':False}
(r/'mac-parity-baseline.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
