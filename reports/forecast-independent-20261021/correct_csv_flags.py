"""V2 report-only clarification: saved forecast actionability vs mature evaluation."""
import argparse,csv,gzip,hashlib,io,json,shutil
from pathlib import Path

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('--original',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists();shutil.copytree(a.original,a.output)
 counts={}
 for family in ['control','stumpy','minirocket','rdst','cnn']:
  d=a.output/family;mature={int(v['row']) for v in json.loads((d/'actionable-forecasts.json').read_text())};censored={int(v['row']):bool(v['actionable_forecast']) for v in json.loads((d/'censored-forecasts.json').read_text())};n=forecasts=evaluated=0
  with gzip.open(a.original/family/'forecasts.csv.gz','rt',newline='') as source,(d/'forecasts.csv.gz').open('wb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as gz,io.TextIOWrapper(gz,encoding='utf-8',newline='') as text:
   reader=csv.DictReader(source);columns=[]
   for name in reader.fieldnames:columns.extend(['actionable_forecast','evaluated_actionable'] if name=='actionable' else [name])
   w=csv.DictWriter(text,columns);w.writeheader()
   for r in reader:
    row=int(r['row']);r.pop('actionable');ev=row in mature;candidate=ev or censored.get(row,False);r['actionable_forecast']=int(candidate);r['evaluated_actionable']=int(ev)
    if int(r['censored']):assert r['direction_truth']=='UNKNOWN' and all(r['truth_'+b+'_'+s]=='' for b in ['lower','upper'] for s in ['long','short']) and not ev and r['actionable_details_json']==''
    w.writerow(r);n+=1;forecasts+=candidate;evaluated+=ev
  assert n==9744 and evaluated==len(mature);counts[family]={'all_origin_actionable_forecast':int(forecasts),'evaluated_actionable':int(evaluated),'rows':n}
 assert counts['stumpy']['all_origin_actionable_forecast']==225 and counts['stumpy']['evaluated_actionable']==223
 schema=json.loads((a.output/'schema.json').read_text());schema['columns']=columns;schema['actionable_flags']={'actionable_forecast':'saved mature actionable membership OR saved censored actionability flag; includes forecasts without mature outcomes','evaluated_actionable':'saved mature actionable membership only; censored always false'};schema['version']=2;schema['report_only_correction']='Clarify two STUMPY censored actionable flags; no prediction, truth, metric or model changes';write(a.output/'schema.json',schema)
 write(a.output/'csv-v2-correction.json',{'status':'REPORT_ONLY_V2_PASS','source_original':str(a.original),'original_manifest_sha256':sha(a.original/'artifact-manifest.json'),'source_correction_sha256':sha(__file__),'counts':counts,'inference_repeated':False,'original_preserved':True})
 (a.output/'artifact-manifest.json').unlink();files=[{'path':str(p.relative_to(a.output)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(a.output.rglob('*')) if p.is_file()];write(a.output/'artifact-manifest.json',{'version':2,'artifacts':files,'total_bytes':sum(p['bytes'] for p in files),'models_or_raw_history_in_export':False});print(json.dumps({'status':'REPORT_ONLY_V2_PASS','output':str(a.output),'counts':counts,'bytes':sum(p['bytes'] for p in files)}))
if __name__=='__main__':main()
