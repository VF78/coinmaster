"""Fixed FAST numerical recognizers. No trading, data building, or automatic fitting."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pickle
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# Must be set before lazy Numba/STUMPY imports; BLAS is scoped in main.
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

CLASS_ORDER = ("UP", "DOWN", "NONE")
TF_NS = (3600 * 10**9, 14400 * 10**9, 86400 * 10**9)
WINDOW = 20
EPS = 1e-12
PANELS = ("BTC1h", "SOL1h", "BTC4h", "SOL4h", "BTC1d", "SOL1d")


def utc_ns(value):
    from datetime import datetime
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 10**9)


def flag(value):
    return str(value).lower() in ("true", "1", "yes")


@dataclass(frozen=True)
class Sample:
    row: int
    sample_id: str
    decision_ns: int
    horizon_end_ns: int
    ready_ns: int
    labels: tuple[int, int]
    selected_train: bool
    eligible: bool
    future_start_index: int | None = None
    future_end_index: int | None = None


def load_samples(path):
    """Never parse U labels. CSV positions still index original N-row memmaps."""
    rows = []
    with Path(path).open(newline="") as stream:
        for i, r in enumerate(csv.DictReader(stream)):
            if r["split"] == "U":
                continue
            labels = (int(r["btc_label"]), int(r["sol_label"]))
            eligible = flag(r["joint_eligible"]) and flag(r["feature_valid"])
            if eligible and any(x not in (0, 1, 2) for x in labels):
                raise ValueError("eligible sample has invalid label")
            rows.append(Sample(i, r["sample_id"], int(r["decision_ns"]),
                               int(r["horizon_end_ns"]),
                               max(int(r["btc_ready_ns"]), int(r["sol_ready_ns"])),
                               labels, flag(r["selected_train"]), eligible,
                               int(r["future_start_index"]) if r.get("future_start_index") not in (None, "") else None,
                               int(r["future_end_index"]) if r.get("future_end_index") not in (None, "") else None))
    if any(a.decision_ns >= b.decision_ns for a, b in zip(rows, rows[1:])):
        raise ValueError("sample decisions must be strictly increasing")
    if len({r.sample_id for r in rows}) != len(rows):
        raise ValueError("duplicate sample IDs")
    if sum(r.selected_train for r in rows) > 6000:
        raise ValueError("common train selection exceeds frozen cap")
    return rows


class Dataset:
    def __init__(self, path):
        self.path = Path(path)
        self.rows = load_samples(self.path / "samples.csv")
        self.features = np.load(self.path / "features.npy", mmap_mode="r")
        self.context = np.load(self.path / "context.npy", mmap_mode="r")
        self.ends = np.load(self.path / "panel_end_indices.npy", mmap_mode="r")
        n = len(self.features)
        if self.features.shape != (n, 6, 20, 6) or self.features.dtype != np.float32:
            raise ValueError("features contract mismatch")
        if self.context.shape != (n, 20) or self.ends.shape != (n, 6):
            raise ValueError("context/end-index contract mismatch")
        self._panels = None

    def panel(self, p):
        if self._panels is None:
            # NpzFile decompresses/copies on each __getitem__; retain six paired arrays once.
            with np.load(self.path / "panels.npz", allow_pickle=False) as archive:
                self._panels = {i: (archive[f"p{i}_available_ns"], archive[f"p{i}_values"])
                                for i in range(6)}
        return self._panels[p]

    def tensor(self, rows, tf):
        ids = [r.row for r in rows]
        # Two assets x six fields, channels in asset-major field order.
        x = self.features[ids, 2*tf:2*tf+2]
        return np.ascontiguousarray(x.transpose(0, 1, 3, 2).reshape(-1, 12, 20))

    def simple(self, rows):
        out = np.empty((len(rows), 38), np.float32)
        out[:, :20] = self.context[[r.row for r in rows]]
        for p in range(6):
            ts, raw = self.panel(p)
            for i, r in enumerate(rows):
                end = int(self.ends[r.row, p])
                if end < 20 or ts[end] > r.decision_ns:
                    raise ValueError("noncausal/incomplete panel")
                close = raw[end-19:end+1, 3]
                out[i, 20+3*p:23+3*p] = np.log(close[-1] / close[[-2, -6, 0]])
        if not np.isfinite(out).all():
            raise ValueError("nonfinite simple features")
        return out


def partition(rows, start, cutoff, predict_end):
    train = [r for r in rows if r.eligible and r.selected_train
             and start <= r.decision_ns < cutoff and r.horizon_end_ns < cutoff]
    test = [r for r in rows if r.eligible and cutoff <= r.decision_ns < predict_end
            and r.horizon_end_ns < predict_end]
    if not train or not test:
        raise ValueError("empty purged train/prediction partition")
    if {r.sample_id for r in train} & {r.sample_id for r in test}:
        raise ValueError("partition overlap")
    return train, test


def prior(labels):
    counts = np.stack([np.bincount(labels[:, a], minlength=3) for a in range(2)])
    return counts / counts.sum(axis=1, keepdims=True)


def align_probabilities(model, x):
    out = np.zeros((len(x), 3), dtype=np.float64)
    out[:, np.asarray(model.classes_, dtype=int)] = model.predict_proba(x)
    return out


def scaled_training_memmap(scaler, x, destination, chunk=128):
    """Same float32 standardized representation, bounded stats and float64 LR storage."""
    if x.dtype != np.float32:
        raise ValueError("dense transform input must stay float32")
    for first in range(0, len(x), chunk):
        scaler.partial_fit(x[first:first+chunk])
    result = np.lib.format.open_memmap(destination, mode="w+", dtype=np.float64,
                                      shape=x.shape, fortran_order=False)
    for first in range(0, len(x), chunk):
        # Preserve the original scaler's float32 output rounding before LR's float64 input.
        block = np.array(x[first:first+chunk], dtype=np.float32, order="C", copy=True)
        scaler.transform(block, copy=False)
        result[first:first+len(block)] = block
    result.flush()  # Clean file-backed pages can be reclaimed under the fixed cap.
    if not result.flags.c_contiguous:
        raise ValueError("LR workspace must be C-contiguous")
    return result


class Heads:
    def fit(self, x, y, workspace=None, chunk=128, consume_input=False):
        from sklearn.preprocessing import StandardScaler
        from sklearn.linear_model import LogisticRegression
        self.scaler = StandardScaler(copy=False)
        if workspace is None:
            train_x = self.scaler.fit_transform(x)
        else:
            train_x = scaled_training_memmap(self.scaler, x, workspace, chunk)
            if consume_input:
                if not isinstance(x, np.memmap):
                    raise ValueError("only an explicitly owned memmap may be consumed")
                x.flush()
                x._mmap.close()  # No obsolete float32 mapping while LBFGS uses the float64 map.
        self.models = []
        self.constants = []
        try:
            for a in range(2):
                classes = np.unique(y[:, a])
                if len(classes) == 1:
                    self.models.append(None)
                    self.constants.append(int(classes[0]))
                else:
                    model = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
                    model.fit(train_x, y[:, a])
                    if int(model.n_iter_.max()) >= 1000:
                        raise RuntimeError("fixed logistic head failed to converge")
                    self.models.append(model)
                    self.constants.append(None)
        finally:
            if workspace is not None:
                train_x._mmap.close()
        return self

    def predict(self, x):
        x = self.scaler.transform(x, copy=False)
        out = np.zeros((len(x), 2, 3), dtype=np.float64)
        for a, model in enumerate(self.models):
            if model is None:
                out[:, a, self.constants[a]] = 1
            else:
                out[:, a] = align_probabilities(model, x)
        return out


def make_transform(kind):
    if kind == "minirocket":
        from aeon.transformations.collection.convolution_based import MiniRocket
        return MiniRocket(n_kernels=2000, random_state=7, n_jobs=1)
    if kind == "rdst":
        from aeon.transformations.collection.shapelet_based import RandomDilatedShapeletTransform
        return RandomDilatedShapeletTransform(max_shapelets=512, proba_normalization=.8,
                                              random_state=7, n_jobs=1)
    raise ValueError(kind)


def transformed(ds, rows, transformers, destination, chunk=128):
    """Disk-backed concatenation; no float64 full transform concatenation."""
    widths = []
    for tf, tr in enumerate(transformers):
        widths.append(tr.transform(ds.tensor(rows[:1], tf)).shape[1])
    out = np.lib.format.open_memmap(destination, mode="w+", dtype=np.float32,
                                   shape=(len(rows), sum(widths)+20))
    for first in range(0, len(rows), chunk):
        part = rows[first:first+chunk]
        offset = 0
        for tf, (tr, width) in enumerate(zip(transformers, widths)):
            z = tr.transform(ds.tensor(part, tf))
            if not np.isfinite(z).all():
                raise ValueError("nonfinite transform")
            out[first:first+len(part), offset:offset+width] = z
            offset += width
        out[first:first+len(part), offset:] = ds.context[[r.row for r in part]]
    out.flush()
    return out, widths


def independent(candidates, separation):
    """Greedy distance ranking, deterministic tie break, elapsed-time spacing."""
    kept = []
    for distance, timestamp, payload in sorted(candidates, key=lambda v: (v[0], v[1])):
        if all(abs(timestamp - old[1]) >= separation for old in kept):
            kept.append((float(distance), int(timestamp), payload))
    return kept


def smooth_analogs(labels, pi):
    if len(labels) < 3:
        return pi.copy()
    counts = np.stack([np.bincount(np.asarray(labels)[:, a], minlength=3) for a in range(2)])
    return (counts + 3*pi) / (len(labels)+3)


def admissible_analog(old, query_ns, historical_end_ns, age, separation):
    return (old.ready_ns <= query_ns and old.horizon_end_ns <= query_ns
            and old.decision_ns-historical_end_ns == age
            and abs(old.decision_ns-query_ns) >= separation)


def historical_continuation(ds, tf, occurrence, sample):
    """Raw observed input and (decision, decision+72h] hourly prices, diagnostic only."""
    decision = int(sample["decision_ns"])
    end = min(int(sample["horizon_end_ns"]), decision+72*TF_NS[0])
    record = {"sample_id": sample["sample_id"], "decision_ns": decision,
              "horizon_end_ns": end, "input_available_end_ns": occurrence["available_end_ns"],
              "sample_trajectory_reference": {
                  "samples_csv": str(ds.path/"samples.csv"),
                  "future_start_index": sample.get("future_start_index"),
                  "future_end_index": sample.get("future_end_index")},
              "source": {"panels": str(ds.path/"panels.npz"),
                         "manifest": str(ds.path/"manifest.json"),
                         "fields": ["open", "high", "low", "close", "volume", "causal_MA20"],
                         "basis": "raw observed Bybit panel prices; not normalized channels"},
              "assets": {}}
    for a, asset in enumerate(("BTC", "SOL")):
        panel = 2*tf+a
        ts, raw = ds.panel(panel)
        e = int(np.searchsorted(ts, occurrence["available_end_ns"]))
        if e < 19 or e >= len(ts) or int(ts[e]) != occurrence["available_end_ns"]:
            raise ValueError("unavailable historical occurrence endpoint")
        if int(ts[e]) > decision:
            raise ValueError("future input in historical diagnostic")
        hour_ts, hour_raw = ds.panel(a)
        lo = int(np.searchsorted(hour_ts, decision, side="right"))
        hi = int(np.searchsorted(hour_ts, end, side="right"))
        future_ts, prices = hour_ts[lo:hi], hour_raw[lo:hi, 3]
        valid = np.isfinite(prices)
        record["assets"][asset] = {
            "input_panel": PANELS[panel],
            "input_available_ns": ts[e-19:e+1].astype(np.int64).tolist(),
            "input_raw_OHLCV_MA20": raw[e-19:e+1].tolist(),
            "future_panel": PANELS[a],
            "future_available_ns": future_ts[valid].astype(np.int64).tolist(),
            "future_raw_close": prices[valid].tolist(),
            "future_missing_hour_bars": int((~valid).sum()),
            "future_expected_hours": int((end-decision)//TF_NS[0]),
            "future_observed_valid_hours": int(valid.sum())}
    return record


def price_match_svg(record, target):
    """Small actual-price preview, separate axes/time scales explicitly labelled."""
    def polyline(values, xs, color, lo, hi, y0):
        points = " ".join(f"{x:.2f},{y0-100*(v-lo)/max(hi-lo,EPS):.2f}"
                          for x, v in zip(xs, values))
        return f'<polyline fill="none" stroke="{color}" points="{points}"/>'
    from html import escape
    body = ['<svg xmlns="http://www.w3.org/2000/svg" width="620" height="350">',
            '<rect width="620" height="350" fill="white"/>',
            f'<text x="12" y="18">Train sample {escape(record["sample_id"])}</text>',
            '<text x="12" y="36">Raw prices: left20 native-TF bars; right hourly continuation (separate time scales)</text>']
    for a, asset in enumerate(("BTC", "SOL")):
        x = record["assets"][asset]
        inputs = np.asarray(x["input_raw_OHLCV_MA20"])[:, 3]
        future = np.asarray(x["future_raw_close"])
        combined = np.r_[inputs, future]
        lo, hi = float(combined.min()), float(combined.max())
        y0 = 165+145*a
        body.append(f'<text x="12" y="{y0-108}">{asset} actual close [{lo:.5g},{hi:.5g}]</text>')
        body.append(polyline(inputs, np.linspace(70,285,20), "#165dcc", lo, hi, y0))
        if len(future):
            xs = 345+250*(np.asarray(x["future_available_ns"],dtype=float)-
                          record["decision_ns"])/(72*TF_NS[0])
            body.append(polyline(future, xs, "#c55320", lo, hi, y0))
        else:
            body.append(f'<text x="345" y="{y0-35}">No observed continuation</text>')
        body.append(f'<line x1="330" x2="330" y1="{y0-105}" y2="{y0}" stroke="#888"/>')
        body.append(f'<text x="70" y="{y0+15}">{x["input_panel"]}20 closed bars</text>')
        body.append(f'<text x="345" y="{y0+15}">decision exclusive → +72h inclusive</text>')
    body.append('</svg>')
    Path(target).write_text("".join(body))


def catalogue_diagnostics(model, ds, rows, output):
    """Separate held-out outcome annotations; never mutate analogue training memory."""
    for item in model.catalogue:
        tf = ("1h", "4h", "1d").index(item["TF"])
        state = model.tf[tf]
        prototype = np.asarray(item["prototype"])
        matched = []
        for r in rows:
            e = int(ds.ends[r.row, 2*tf])
            q = np.concatenate([raw_channels(ds.panel(2*tf+a)[1][e-20:e+1],
                                              *state["scales"][a])[:, -20:]
                                for a in (0, 1)])
            distance = float(np.linalg.norm(q-prototype, axis=1).mean())
            if distance <= state["threshold"]:
                matched.append((distance, r.decision_ns, r))
        independent_matches = independent(matched, state["separation"])
        item["heldout_independent_matches"] = len(independent_matches)
        item["heldout_label_counts_BTC_SOL"] = [
            np.bincount([x[2].labels[a] for x in independent_matches], minlength=3).tolist()
            for a in (0, 1)]
        item["heldout_examples"] = [{"sample_id": x[2].sample_id,
                                     "distance": x[0], "decision_ns": x[1],
                                     "horizon_end_ns": x[2].horizon_end_ns}
                                    for x in independent_matches[:5]]
    # Historical independent TRAIN matches and genuine continuations, never feature inputs.
    preview_patterns = sorted(model.catalogue,
                              key=lambda x: sum(bool(o["train_samples"]) for o in x["occurrences"]),
                              reverse=True)[:3]
    for item in preview_patterns:
        tf = ("1h", "4h", "1d").index(item["TF"])
        eligible = [o for o in item["occurrences"] if o["train_samples"]]
        examples = []
        for occurrence in eligible[:2]:
            sample = min(occurrence["train_samples"], key=lambda r: r["decision_ns"])
            examples.append(historical_continuation(ds, tf, occurrence, sample))
        item["train_price_preview_status"] = (
            "TWO_INDEPENDENT_TRAIN_MATCHES" if len(examples) >= 2
            else "INSUFFICIENT_COMMON_TRAIN_MATCHES")
        item["available_independent_occurrences_with_train_ID"] = len(eligible)
        item["train_price_examples"] = examples
        for i, record in enumerate(examples):
            name = f'{item["pattern_id"]}-train-match-{i+1}.svg'
            price_match_svg(record, Path(output)/name)
            record["preview_svg"] = name
    # A missing catalogue or fewer than3 patterns stays explicit; nothing is fabricated.


def raw_channels(values, sigma, vmean, vstd):
    result = np.full((6, len(values)), np.nan)
    previous = np.r_[np.nan, values[:-1, 3]]
    for field in (0, 1, 2, 3, 5):
        result[field] = np.log(np.maximum(values[:, field], EPS) /
                               np.maximum(previous, EPS)) / sigma
    result[4] = (np.log1p(np.maximum(values[:, 4], 0))-vmean)/vstd
    result[:, ~np.isfinite(values).all(axis=1)] = np.nan
    result[:, 0] = np.nan
    return result


def fit_scale(ts, values, start, cutoff):
    mask = (ts >= start) & (ts < cutoff)
    previous = np.r_[np.nan, values[:-1, 3]]
    returns = np.log(np.maximum(values[:, 3], EPS)/np.maximum(previous, EPS))
    valid = mask & np.isfinite(returns) & np.isfinite(values).all(axis=1)
    volume = np.log1p(values[valid, 4])
    if valid.sum() < WINDOW:
        raise ValueError("insufficient continuous train values for scaling")
    return (max(float(np.std(returns[valid], ddof=0)), EPS),
            float(np.mean(volume)), max(float(np.std(volume, ddof=0)), EPS))


class Analog:
    def fit(self, ds, train, start, cutoff):
        import stumpy
        import numba
        numba.set_num_threads(1)
        self.prior = prior(np.array([r.labels for r in train]))
        self.tf = []
        self.catalogue = []
        for tf, step in enumerate(TF_NS):
            panels = [ds.panel(2*tf+a) for a in (0, 1)]
            if not np.array_equal(panels[0][0], panels[1][0]):
                raise ValueError("paired native clocks differ")
            ts = panels[0][0]
            if np.any(np.diff(ts) != step):
                raise ValueError("native clock gap must be retained as NaN bar")
            scales = [fit_scale(t, v, start, cutoff) for t, v in panels]
            train_stop = int(np.searchsorted(ts, cutoff, side="left"))
            channels = np.concatenate([raw_channels(v[:train_stop], *s)
                                       for (_, v), s in zip(panels, scales)])
            positions = np.flatnonzero((ts >= start) & (ts < cutoff))
            if not len(positions) or np.any(np.diff(positions) != 1):
                raise ValueError("training native time slice is not contiguous")
            offset = int(positions[0])
            history = channels[:, positions]
            begin = time.perf_counter()
            P, I = stumpy.mstump(history, m=20, normalize=False, p=2.0)
            separation = max(20*step, 72*TF_NS[0])
            nontrivial = []
            # Recalculate in match's mean-per-channel L2 units.
            for j, neighbor in enumerate(I[11]):
                k = int(neighbor)
                if k >= 0 and abs(j-k)*step >= separation:
                    q, h = history[:, j:j+20], history[:, k:k+20]
                    if q.shape == (12, 20) and h.shape == (12, 20):
                        distance = np.linalg.norm(q-h, axis=1).mean()
                        if np.isfinite(distance):
                            nontrivial.append(float(distance))
            if not nontrivial:
                raise ValueError("no independent train nearest-neighbor distances")
            threshold = float(np.quantile(nontrivial, .9, method="linear"))
            distances, indices, _, _ = stumpy.mmotifs(
                history, P, I, k=11, normalize=False, p=2.0,
                max_distance=threshold, max_motifs=8, min_neighbors=3, max_matches=50)
            by_end = {}
            for r in train:
                e = int(ds.ends[r.row, 2*tf])
                by_end.setdefault(e, []).append(r)
            entries = []
            for motif, (dd, ii) in enumerate(zip(distances, indices)):
                candidates = [(float(d), int(ts[offset+int(i)+19]), int(i))
                              for d, i in zip(dd, ii) if i >= 0 and np.isfinite(d)]
                kept = independent(candidates, separation)
                if len(kept) < 3:
                    continue
                first = kept[0][2]
                occurrences = []
                for distance, endpoint, index in kept:
                    end_index = offset+index+19
                    samples = by_end.get(end_index, [])
                    occurrences.append({
                        "start_ns": int(ts[offset+index]), "available_end_ns": endpoint,
                        "distance": distance,
                        "train_samples": [{"sample_id": r.sample_id, "decision_ns": r.decision_ns,
                                           "age_ns": r.decision_ns-endpoint,
                                           "labels": list(r.labels), "horizon_end_ns": r.horizon_end_ns,
                                           "future_start_index": r.future_start_index,
                                           "future_end_index": r.future_end_index}
                                          for r in samples]})
                entries.append({"pattern_id": f"TF{tf}-{motif}", "TF": ("1h", "4h", "1d")[tf],
                                "channels": 12, "independent_episodes": len(kept),
                                "prototype": history[:, first:first+20].tolist(),
                                "occurrences": occurrences})
            self.catalogue.extend(entries)
            self.tf.append({"history": history, "ts": ts[:train_stop],
                            "offset": offset, "threshold": threshold, "scales": scales,
                            "by_end": by_end, "separation": separation,
                            "threshold_count": len(nontrivial),
                            "fit_seconds": time.perf_counter()-begin})
        return self

    def predict(self, ds, rows):
        import stumpy
        result = np.zeros((len(rows), 2, 3))
        coverage = np.zeros((len(rows), 3), np.int32)
        # One query at a time; no market pair-distance matrix.
        for i, r in enumerate(rows):
            for tf, state in enumerate(self.tf):
                end = int(ds.ends[r.row, 2*tf])
                query_ts, _ = ds.panel(2*tf)
                age = r.decision_ns-int(query_ts[end])
                q = np.concatenate([raw_channels(ds.panel(2*tf+a)[1][end-20:end+1],
                                                  *state["scales"][a])[:, -20:]
                                    for a in (0, 1)])
                if q.shape != (12, 20) or not np.isfinite(q).all():
                    raise ValueError("invalid eligible query")
                matches = stumpy.match(q, state["history"], normalize=False, p=2,
                                       max_matches=50, max_distance=state["threshold"])
                candidates = []
                for distance, index in matches:
                    e = state["offset"]+int(index)+19
                    for old in state["by_end"].get(e, []):
                        if not admissible_analog(old, r.decision_ns, int(state["ts"][e]),
                                                 age, state["separation"]):
                            continue
                        candidates.append((float(distance), old.decision_ns, old))
                kept = independent(candidates, state["separation"])
                coverage[i, tf] = len(kept)
                result[i] += smooth_analogs([x[2].labels for x in kept], self.prior)/3
        return result, coverage


def metrics(rows, probabilities):
    y = np.asarray([r.labels for r in rows])
    p = np.asarray(probabilities)
    if p.shape != (len(rows), 2, 3) or not np.isfinite(p).all():
        raise ValueError("invalid prediction shape/values")
    if np.any(p < 0) or not np.allclose(p.sum(axis=2), 1, atol=1e-6):
        raise ValueError("probabilities must be normalized")
    result = {}
    for a, asset in enumerate(("BTC", "SOL")):
        truth = np.eye(3)[y[:, a]]
        loss = -np.log(np.clip(p[np.arange(len(y)), a, y[:, a]], EPS, 1))
        bins = []
        for c in range(3):
            for low in range(10):
                mask = (p[:, a, c] >= low/10) & ((p[:, a, c] < (low+1)/10)
                        if low < 9 else (p[:, a, c] <= 1))
                if mask.any():
                    bins.append({"class": c, "bin": low, "n": int(mask.sum()),
                                 "mean_probability": float(p[mask, a, c].mean()),
                                 "observed_frequency": float(truth[mask, c].mean())})
        blocks = {}
        for i, r in enumerate(rows):
            month = np.datetime_as_string(np.datetime64(r.decision_ns, "ns"), unit="M")
            blocks.setdefault(month, []).append(float(loss[i]))
        result[asset] = {"log_loss": float(loss.mean()),
                         "brier_sum_classes": float(np.square(p[:, a]-truth).sum(axis=1).mean()),
                         "class_frequency": truth.mean(axis=0).tolist(), "calibration": bins,
                         "monthly_log_loss": {k: {"n": len(v), "log_loss": float(np.mean(v))}
                                              for k, v in blocks.items()}}
    result["mean_log_loss"] = (result["BTC"]["log_loss"]+result["SOL"]["log_loss"])/2
    result["n"] = len(rows)
    result["independent_72h_episodes"] = len(independent(
        [(0, r.decision_ns, None) for r in rows], 72*TF_NS[0]))
    return result


def rdst_explanations(transformers, heads, widths, train_z, train):
    """Coefficients rank associations, not causes; transformed coordinates give real matches."""
    items = []
    offset = 0
    for tf, (tr, width) in enumerate(zip(transformers, widths)):
        for a, model in enumerate(heads.models):
            if model is None:
                continue
            scores = np.abs(model.coef_[:, offset:offset+width]).max(axis=0)
            for feature in np.argsort(scores)[-3:][::-1]:
                shapelet = int(feature)//3
                # Exact learned shapelets remain in the serialized transformer.
                items.append({"TF": tf, "asset": ("BTC", "SOL")[a],
                              "feature": int(feature), "shapelet_index": shapelet,
                              "coefficient_abs_max": float(scores[feature]),
                              "note": "real matched sample by minimum learned-shapelet distance; no causal interpretation",
                              "minimum_distance_sample_id": train[
                                  int(np.argmin(train_z[:, offset+3*shapelet]))].sample_id})
        offset += width
    return items


def run(dataset, lock_path, output, stage, fold):
    start_clock = time.perf_counter()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    lock = json.loads(Path(lock_path).read_text())
    ds = Dataset(dataset)
    start = utc_ns(lock["T"][0])
    cuts = [utc_ns(x) for x in lock["OOF_fit_cutoffs"]]
    f = ("oof20", "oof40", "validation").index(fold)
    cutoff = cuts[f]
    end = cuts[f+1] if f < 2 else utc_ns(lock["V"][1])
    train, test = partition(ds.rows, start, cutoff, end)
    y = np.array([r.labels for r in train])
    recipe = {"stage": stage, "fold": fold, "fit_cutoff_ns": cutoff,
              "prediction_end_ns": end, "class_order": CLASS_ORDER,
              "train_n": len(train), "prediction_n": len(test),
              "train_ids_sha256": hashlib.sha256("\n".join(r.sample_id for r in train).encode()).hexdigest(),
              "prediction_ids_sha256": hashlib.sha256("\n".join(r.sample_id for r in test).encode()).hexdigest(),
              "purge": "horizon_end_ns strictly less than next partition start; full72h",
              "seed": 7, "n_jobs": 1, "pending_U": "not read or predicted",
              "lock_sha256": hashlib.sha256(Path(lock_path).read_bytes()).hexdigest()}
    fit_clock = time.perf_counter()
    model = None
    coverage = None
    extra = {}
    if stage == "prior":
        pi = prior(y)
        fit_seconds = time.perf_counter()-fit_clock
        infer_clock = time.perf_counter()
        probabilities = np.broadcast_to(pi, (len(test), 2, 3)).copy()
        model = pi
    elif stage == "stumpy":
        model = Analog().fit(ds, train, start, cutoff)
        fit_seconds = time.perf_counter()-fit_clock
        infer_clock = time.perf_counter()
        probabilities, coverage = model.predict(ds, test)
        catalogue_diagnostics(model, ds, test, output)
        (output/"catalogue.json").write_text(json.dumps({
            "patterns": model.catalogue,
            "TF": [{k: state[k] for k in ("threshold", "threshold_count", "fit_seconds", "scales")}
                   for state in model.tf],
            "threshold": "linear P90 independent train nearest-neighbor mean-channel L2 distances",
            "validation_labels_never_enter_memory": True,
            "train_price_preview_requested_pattern_max": 3,
            "actual_catalogue_patterns": len(model.catalogue),
            "train_price_preview_note": "Up to2 independent common-train occurrences per displayed pattern; insufficient examples remain explicit"}, allow_nan=False))
        extra["analogue_coverage_ge3_per_TF"] = (coverage >= 3).mean(axis=0).tolist()
        extra["analogue_count_ge3_per_TF"] = (coverage >= 3).sum(axis=0).tolist()
        extra["analogue_count_ge3_any_TF"] = int((coverage >= 3).any(axis=1).sum())
        extra["analogue_coverage_ge3_any_TF"] = float((coverage >= 3).any(axis=1).mean())
    else:
        if stage == "simple":
            x = ds.simple(train)
            model = Heads().fit(x, y)
            fit_seconds = time.perf_counter()-fit_clock
            infer_clock = time.perf_counter()
            probabilities = model.predict(ds.simple(test))
        else:
            transformers = []
            for tf in range(3):
                tr = make_transform(stage)
                tr.fit(ds.tensor(train, tf))  # Deliberately WITHOUT labels for both transforms.
                transformers.append(tr)
            z, widths = transformed(ds, train, transformers, output/"train-transform.npy")
            head_workspace = output/"head-train-float64.npy"
            model_heads = Heads().fit(z, y, workspace=head_workspace, consume_input=True)
            del z  # The input mapping was explicitly closed before the two LR fits.
            extra["actual_TF_feature_counts"] = widths
            if stage == "minirocket":
                extra["requested_kernels"] = 2000
                extra["expected_effective_per_TF"] = 1932
                if widths != [1932]*3:
                    raise ValueError("unexpected pinned MiniRocket output width")
            if stage == "rdst":
                standardized_z = np.load(head_workspace, mmap_mode="r")
                try:
                    extra["shapelets_explanation"] = rdst_explanations(
                        transformers, model_heads, widths, standardized_z, train)
                finally:
                    standardized_z._mmap.close()
            fit_seconds = time.perf_counter()-fit_clock
            infer_clock = time.perf_counter()
            predict_z, _ = transformed(ds, test, transformers, output/"prediction-transform.npy")
            probabilities = np.empty((len(test), 2, 3))
            for first in range(0, len(test), 128):
                probabilities[first:first+128] = model_heads.predict(predict_z[first:first+128])
            model = {"transformers": transformers, "heads": model_heads, "widths": widths}
    infer_seconds = time.perf_counter()-infer_clock
    result = metrics(test, probabilities)
    result.update(recipe)
    result.update(extra)
    import resource
    result.update({"fit_seconds": fit_seconds, "inference_seconds": infer_seconds,
                   "elapsed_seconds": time.perf_counter()-start_clock,
                   "process_maxrss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024})
    with (output/"predictions.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["sample_id", "decision_ns"]+[f"{a}_{c}" for a in ("BTC", "SOL") for c in CLASS_ORDER]
                        + (["analogs_1h", "analogs_4h", "analogs_1d"] if coverage is not None else []))
        for i, r in enumerate(test):
            writer.writerow([r.sample_id, r.decision_ns]+probabilities[i].ravel().tolist()
                            +(coverage[i].tolist() if coverage is not None else []))
    with (output/"model.pkl").open("wb") as stream:
        pickle.dump(model, stream, protocol=5)
    (output/"metrics.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    # Temporary transforms are private numeric intermediates, not model artifacts.
    for name in ("train-transform.npy", "prediction-transform.npy", "head-train-float64.npy"):
        path = output/name
        if path.exists():
            path.unlink()
    return result


def select_recognizer(reports):
    """Selection waits for the mandatory CNN report and identical validation IDs."""
    required = {"prior", "simple", "stumpy", "minirocket", "rdst", "cnn"}
    if not required.issubset(reports):
        return {"status": "PENDING_ALL_FOUR_AND_CONTROLS",
                "missing": sorted(required-set(reports))}
    ids = {reports[k]["prediction_ids_sha256"] for k in required}
    if len(ids) != 1 or any(reports[k]["fold"] != "validation" for k in required):
        raise ValueError("selection needs identical validation IDs and split")
    control = reports["simple"]
    eligible = [k for k in ("stumpy", "minirocket", "rdst", "cnn")
                if reports[k]["BTC"]["log_loss"] <= control["BTC"]["log_loss"]
                and reports[k]["mean_log_loss"] <
                min(control["mean_log_loss"], reports["prior"]["mean_log_loss"])]
    if not eligible:
        return {"status": "NO_ADDED_DIAGNOSTIC_INFORMATION"}
    best = min(eligible, key=lambda k: reports[k]["mean_log_loss"])
    best_loss = reports[best]["mean_log_loss"]
    ties = [k for k in eligible
            if (reports[k]["mean_log_loss"]-best_loss)/max(best_loss, EPS) < .01]
    complexity = {"stumpy": 0, "minirocket": 1, "rdst": 2, "cnn": 3}
    chosen = min(ties, key=lambda k: (reports[k]["fit_seconds"]+
                                    reports[k]["inference_seconds"], complexity[k]))
    return {"status": "DIAGNOSTIC_ONLY_NO_ROI_CLAIM", "chosen": chosen,
            "lowest_log_loss": best, "tie_relative_denominator": "lowest_mean_log_loss",
            "BTC_safeguard": "not worse than simple control",
            "tie_candidates": ties}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--lock", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("prior", "simple", "stumpy", "minirocket", "rdst"), required=True)
    parser.add_argument("--fold", choices=("oof20", "oof40", "validation"), required=True)
    parser.add_argument("--execute-fit", action="store_true",
                        help="requires separate root GO; default is a command plan only")
    args = parser.parse_args()
    if not args.execute_fit:
        print(json.dumps({"status": "PLAN_ONLY_NO_DATA_READ_NO_FIT", **vars(args)}))
        return
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        result = run(args.dataset, args.lock, args.output, args.stage, args.fold)
    print(json.dumps({k: result[k] for k in ("stage", "fold", "train_n", "prediction_n",
                                           "mean_log_loss", "fit_seconds", "inference_seconds")}))


if __name__ == "__main__":
    # Stable module-qualified pickle classes, even when invoked with python -m.
    from coinmaster.research.fast_numeric import main as canonical_main
    canonical_main()
