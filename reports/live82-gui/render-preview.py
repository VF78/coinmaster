"""Isolated fixture preview. GET-only; never relays worker commands."""
import copy, functools, http.server, io, json, sys, time, urllib.parse
from pathlib import Path
sys.path.insert(0, str(Path("runtime").resolve()))
from coinmaster.api import runtime_sidecar as api

sandbox = api.HlStagegProjectionReader("http://127.0.0.1:18183").runtime().model_dump()
planned = api.HlLiveStrategyReader().strategy().model_dump()
strategy = api.HlStagegStrategyReader().strategy().model_dump()
empty = api.HlLiveProjectionReader.unavailable("UNAVAILABLE", "LIVE_WORKER_UNAVAILABLE").model_dump()
live = copy.deepcopy(empty)
live.update(projection_state="READY", observed_at_ns=time.time_ns(), live_order_capability=True,
            native_thread_alive=True, recovery_required=False, process_state="PUBLIC_FEEDS_READY",
            reconciliation="CURRENT", run_epoch="fixture-live-epoch", warnings=[],
            profile={"profile_id":"V3+DP50", "initial_capital_usdc":"82"},
            account={"native_cash":"81.5", "equity":"82.3", "native_free":"70", "native_locked":"11.5",
                     "observed_at_ns":time.time_ns()}, entry_control={"state":"RUNNING","capability":"READY"},
            gates={"attachable":True})
def fresh(payload):
    result=copy.deepcopy(payload)
    if result.get("projection_state") == "READY":
        result["observed_at_ns"]=time.time_ns()
        result["account"]["observed_at_ns"]=time.time_ns()
    return result
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory="coinmaster/dist",**kwargs)
    def log_message(self,*args): pass
    def do_POST(self):
        self.send_error(405, "Read-only fixture preview")
    def do_GET(self):
        path=urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/"): return super().do_GET()
        query=urllib.parse.parse_qs(urllib.parse.urlparse(self.headers.get("Referer","")).query)
        scenario=query.get("scenario",["inactive"])[0]
        selected="hl-stageg-live" if "/hl-stageg-live" in path else "hl-stageg-testnet"
        projection=fresh(live if scenario=="current" else empty) if selected=="hl-stageg-live" else fresh(sandbox)
        if scenario=="stale" and selected=="hl-stageg-live": projection.update(projection_state="STALE", warnings=["LIVE_STATUS_STALE"])
        suffix=path.split(selected)[-1] if selected in path else None
        if suffix=="": payload=projection
        elif suffix=="/strategy": payload=planned if selected=="hl-stageg-live" else strategy
        elif suffix=="/controls": payload=api.hl_stageg_controls(api.HlStagegProjection.model_validate(projection),False).model_dump()
        elif suffix=="/fills": payload={"version":"hl-stageg-fills-v1","instance_id":selected,"run_epoch":projection.get("run_epoch"),"state":"UNAVAILABLE","fills":[],"next_cursor":0,"has_more":False,"historical_id_only_count":None,"reason":"FIXTURE"}
        elif suffix=="/equity-changes": payload={"state":"UNAVAILABLE","windows":{}}
        elif path=="/api/v1/connections": payload={"connections":[],"display_connection_id":None}
        elif path=="/api/v1/connections/mode": payload={"sandbox":{"state":"RUNNING"},"live":{"state":"INACTIVE"},"activate_enabled":False,"stop_enabled":False,"blockers":["Separate exact Live order approval is required"],"stop_reason":"Separate permission required"}
        elif path=="/api/v1/configurations": payload=[]
        elif "/markets/" in path: payload={"state":"UNAVAILABLE","candles":[]}
        else: payload={}
        Path("reports/live82-gui/render-requests.jsonl").open("a").write(json.dumps({"method":"GET","path":path,"scenario":scenario})+"\n")
        data=json.dumps(payload).encode()
        self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
http.server.ThreadingHTTPServer(("127.0.0.1",18991),Handler).serve_forever()
