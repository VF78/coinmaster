"""Freeze CM2 design points without reading outcomes or constructing an engine."""
from dataclasses import asdict
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import random
from coinmaster.strategy.cm2_policy import Config
import coinmaster.strategy.cm2_policy as policy_module

HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def sample(space):
    try:
        from scipy.stats import qmc
    except ImportError:
        rng = random.Random(space["seed"])
        vectors = [[rng.random() for _ in range(7)] for _ in range(space["count"])]
        method = "SEEDED_UNIFORM_NOT_SOBOL"
        implementation = "stdlib random.Random(20261031), row-major64x7 random()"
    else:
        vectors = qmc.Sobol(d=7, scramble=True, seed=space["seed"]).random_base2(m=6).tolist()
        method = "SCRAMBLED_SOBOL"
        implementation = space["preferred_sampler"]
    return vectors, {"method": method, "implementation": implementation, "seed": space["seed"],
                     "python": platform.python_version(), "scipy": version("scipy"), "numpy": version("numpy")}


def transform(vector, space):
    if len(vector) != 7 or not all(0 <= u <= 1 for u in vector):
        raise ValueError("EXACT_SEVEN_UNIT_COORDINATES_REQUIRED")
    values = {}
    for u, spec in zip(vector, space["parameters"]):
        lo, hi = spec["lower"], spec["upper"]
        x = (math.exp(math.log(lo) + u * (math.log(hi) - math.log(lo)))
             if spec["scale"] == "log" else lo + u * (hi - lo))
        values[spec["name"]] = math.floor(x + .5) if spec["name"] == "trend_hours" else round(x, 6)
    values.update(space["fixed_policy"])
    return asdict(Config(**values))


def build():
    space_bytes = (HERE / "SPACE.json").read_bytes()
    space = json.loads(space_bytes)
    vectors, sampler = sample(space)
    cases = []
    seen = set()
    for i, vector in enumerate(vectors):
        policy = transform(vector, space)
        digest = sha(canonical(policy))
        if digest in seen:
            raise ValueError("POST_ROUNDING_DUPLICATE_NO_REPLACEMENT")
        seen.add(digest)
        cases.append({"index": i, "run_id": f"CM2_BROAD_V1_{i:03d}", "u": vector,
                      "policy": policy, "policy_sha256": digest,
                      "block": "INITIAL32_PENDING_ROOT_GO" if i < 32 else "CONDITIONAL32_HOLD"})
    if len(cases) != 64:
        raise ValueError("EXACT64_REQUIRED")
    return {"schema": "cm2-frozen64-v1", "task_id": "CM2_CLEAN_HEDGE_20261031", "count": 64,
            "space_sha256": sha(space_bytes), "space_canonical_sha256": sha(canonical(space)),
            "generator_sha256": sha(Path(__file__).read_bytes()),
            "validator_source_sha256": sha(Path(policy_module.__file__).read_bytes()),
            "validator_source_base_commit": "77935a3938d036be76bb8935e6c1eb925505d359",
            "sampler": sampler, "cases": cases,
            "dispatch_authority": "NONE; immutable design only; exact JSON must be reused across hosts"}


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.freeze == args.verify:
        parser.error("choose --freeze ONCE or --verify read-only")
    raw = encoded(build())
    target = HERE / "FROZEN64.json"
    if args.verify:
        if target.read_bytes() != raw:
            raise ValueError("FROZEN64_REPRODUCTION_MISMATCH_USE_ORIGINAL_JSON")
    else:
        with target.open("xb") as stream:
            stream.write(raw)
    print(json.dumps({"path": str(target), "sha256": sha(raw), "count": 64,
                      "action": "VERIFIED_NO_WRITE" if args.verify else "FROZEN_ONCE",
                      "dispatch_authority": "NONE"}, sort_keys=True))


if __name__ == "__main__":
    main()
