"""Read-only immutable research pack validator; no engine execution."""
import hashlib,json,sys
from pathlib import Path
ALLOWLIST=["runtime/coinmaster","runtime/configs","runtime/scripts","runtime/pyproject.toml","runtime/uv.lock","runtime/var/venue-manifest.json","runtime/var/raw/venues"]
job=Path(sys.argv[1]); expected=json.loads((job/"immutable-source-hashes.json").read_text())
for name,digest in expected.items():
 assert hashlib.sha256((job/"source"/name).read_bytes()).hexdigest()==digest,name
assert "var/venue-manifest.json" in expected
assert any(name.startswith("var/raw/venues/") for name in expected)
assert not (job/"source/.env").exists()
print(json.dumps({"job":str(job),"validated_files":len(expected),"public_metadata_files":sum(name.startswith("var/raw/venues/") or name=="var/venue-manifest.json" for name in expected),"allowlist":ALLOWLIST,"code_commit":(job/"source-commit.txt").read_text().strip()}))
