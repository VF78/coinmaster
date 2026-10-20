"""Fixed FAST CNN recipe; lazy rendering, no implicit fitting or U access."""
from __future__ import annotations
import argparse
import csv
import gc
import hashlib
import json
import random
import sys
import struct
import zlib
import time
from pathlib import Path
import numpy as np

SEEDS = (7, 42)
MAX_EPOCHS = 30
PATIENCE = 2
PARAMETERS = 898110
BATCH_SIZE = 128
CLASS_ORDER = ("UP", "DOWN", "NONE")
RENDERER = {"shape": [6, 64, 60], "price_rows": [0, 47],
            "divider_rows": [48, 49], "volume_rows": [50, 63],
            "rounding": "numpy.rint nearest ties-even", "MA": "integer Bresenham",
            "volume_width": "one center pixel", "pixels": "float32 binary"}


def _line(image, x0, y0, x1, y1):
    dx, dy = abs(x1-x0), -abs(y1-y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx+dy
    while True:
        image[y0, x0] = 1
        if x0 == x1 and y0 == y1:
            break
        twice = 2*err
        if twice >= dy:
            err += dy; x0 += sx
        if twice <= dx:
            err += dx; y0 += sy


def render(normalized):
    """One shared (panel,bar,O/H/L/C/V/MA) record; no prices or future inputs."""
    values = np.asarray(normalized)
    if values.shape != (6, 20, 6):
        raise ValueError("CNN_FEATURE_SHAPE")
    if not np.isfinite(values).all() or np.any(values < 0) or np.any(values > 1):
        raise ValueError("CNN_FEATURE_NOT_FINITE_NORMALIZED")
    image = np.zeros((6, 64, 60), dtype=np.float32)
    y = np.rint((1-values[:, :, [0, 1, 2, 3, 5]])*47).astype(np.int64)
    heights = np.rint(values[:, :, 4]*14).astype(np.int64)
    for p in range(6):
        for j in range(20):
            x = 3*j+1
            opened, high, low, close, ma = y[p, j]
            if high > low or not high <= opened <= low or not high <= close <= low:
                raise ValueError("CNN_NORMALIZED_OHLC_ORDER")
            image[p, high:low+1, x] = 1
            image[p, opened, x-1:x+1] = 1
            image[p, close, x:x+2] = 1
            if j:
                _line(image[p], x-3, int(y[p, j-1, 4]), x, int(ma))
            else:
                image[p, ma, x] = 1
            if heights[p, j]:
                image[p, 64-heights[p, j]:64, x] = 1
    return image


class ContextScaler:
    """StandardScaler convention: train mean/std(ddof=0), constants scale=1."""
    def fit(self, values):
        x = np.asarray(values, dtype=np.float64)
        if x.ndim != 2 or x.shape[1] != 20 or not len(x) or not np.isfinite(x).all():
            raise ValueError("CNN_CONTEXT_TRAIN")
        self.mean = x.mean(0)
        self.scale = x.std(0)
        self.scale[self.scale == 0] = 1
        return self

    def transform(self, values):
        x = np.asarray(values, dtype=np.float64)
        if x.ndim != 2 or x.shape[1] != 20 or not np.isfinite(x).all():
            raise ValueError("CNN_CONTEXT_INPUT")
        return ((x-self.mean)/self.scale).astype(np.float32)


def batches(ds, rows, scaler, batch_size, shuffle_seed=None):
    """Only one image batch is resident; original memmap row numbers are retained."""
    if batch_size < 1 or batch_size > BATCH_SIZE:
        raise ValueError("CNN_BATCH_BOUNDS")
    order = np.arange(len(rows))
    if shuffle_seed is not None:
        np.random.default_rng(shuffle_seed).shuffle(order)
    for first in range(0, len(order), batch_size):
        selected = [rows[int(i)] for i in order[first:first+batch_size]]
        ids = [r.row for r in selected]
        images = np.stack([render(ds.features[i]) for i in ids])
        context = scaler.transform(ds.context[ids])
        labels = np.asarray([r.labels for r in selected], dtype=np.int64)
        yield images, context, labels


def build_model():
    """Torch is deliberately imported only when this explicit factory is called."""
    import torch
    from torch import nn

    class FixedCNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(6, 64, (5, 3), stride=(3, 1), dilation=(2, 1), padding=(4, 1)),
                nn.BatchNorm2d(64), nn.LeakyReLU(.01),
                nn.MaxPool2d((2, 1), stride=(2, 1), ceil_mode=True),
                nn.Conv2d(64, 128, (5, 3), padding=(2, 1)),
                nn.BatchNorm2d(128), nn.LeakyReLU(.01),
                nn.MaxPool2d((2, 1), stride=(2, 1), ceil_mode=True),
                nn.Conv2d(128, 256, (5, 3), padding=(2, 1)),
                nn.BatchNorm2d(256), nn.LeakyReLU(.01),
                nn.MaxPool2d((2, 1), stride=(2, 1), ceil_mode=True))
            self.head = nn.Sequential(nn.Dropout(.5), nn.Linear(46080+20, 6))
            for layer in self.modules():
                if isinstance(layer, (nn.Conv2d, nn.Linear)):
                    nn.init.xavier_uniform_(layer.weight)
                    nn.init.zeros_(layer.bias)

        def forward(self, images, context):
            features = self.features(images)
            if tuple(features.shape[1:]) != (256, 3, 60) or context.shape != (len(images), 20):
                raise ValueError("CNN_FORWARD_SHAPE")
            return self.head(torch.cat((features.flatten(1), context), dim=1))

    model = FixedCNN()
    assert sum(p.numel() for p in model.parameters()) == PARAMETERS
    return model


def joint_loss(logits, labels):
    import torch.nn.functional as F
    return .5*F.cross_entropy(logits[:, :3], labels[:, 0]) + .5*F.cross_entropy(logits[:, 3:], labels[:, 1])


class EpochChoice:
    def __init__(self):
        self.best_loss, self.best_epoch, self.stale = float("inf"), 0, 0

    def observe(self, epoch, loss):
        if not np.isfinite(loss):
            raise ValueError("CNN_NONFINITE_INNER_LOSS")
        if loss < self.best_loss:
            self.best_loss, self.best_epoch, self.stale = loss, epoch, 0
        else:
            self.stale += 1
        return self.stale >= PATIENCE


def partitions(rows, lock, fold):
    from coinmaster.research.fast_numeric import partition, utc_ns
    f = ("oof20", "oof40", "validation").index(fold)
    start = utc_ns(lock["T"][0])
    cuts = [utc_ns(x) for x in lock["OOF_fit_cutoffs"]]
    cutoff = cuts[f]
    end = cuts[f+1] if f < 2 else utc_ns(lock["V"][1])
    if end > utc_ns(lock["U"][0]) or cutoff >= utc_ns(lock["U"][0]):
        raise ValueError("CNN_U_CLOSED")
    train, predict = partition(rows, start, cutoff, end)
    # OOF selects its own past-only epoch; never reuse a later fold's epoch.
    inner = utc_ns(lock["CNN_inner_T_split"]) if fold == "validation" else start+(cutoff-start)*85//100
    inner_train = [r for r in train if r.decision_ns < inner and r.horizon_end_ns < inner]
    inner_validation = [r for r in train if r.decision_ns >= inner]
    if not inner_train or not inner_validation:
        raise ValueError("CNN_EMPTY_PURGED_INNER_PARTITION")
    return train, predict, inner_train, inner_validation, cutoff, end, inner


def _seed(seed):
    import torch
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def _evaluate_loss(model, ds, rows, scaler, batch_size):
    import torch
    total = 0.
    model.eval()
    with torch.inference_mode():
        for image, context, y in batches(ds, rows, scaler, batch_size):
            loss = joint_loss(model(torch.from_numpy(image), torch.from_numpy(context)), torch.from_numpy(y))
            total += float(loss)*len(y)
    return total/len(rows)


def _emit_progress(event, seed, phase, batch_size, **fields):
    print(json.dumps({"event": event, "seed": seed, "phase": phase,
                      "batch_size": batch_size, **fields}, sort_keys=True),
          file=sys.stderr, flush=True)


def _fit_once(ds, train, validation, seed, batch_size, epochs=None):
    import torch
    phase = "inner" if validation is not None else "refit"
    _emit_progress("CNN_STAGE_START", seed, phase, batch_size, timestamp_ns=time.time_ns())
    _seed(seed)
    scaler = ContextScaler().fit(ds.context[[r.row for r in train]])
    model = build_model()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-5)
    choice, history = EpochChoice(), []
    for epoch in range(1, (MAX_EPOCHS if epochs is None else epochs)+1):
        started = time.perf_counter()
        model.train()
        total = 0.
        for image, context, y in batches(ds, train, scaler, batch_size, seed+epoch):
            optimizer.zero_grad(set_to_none=True)
            loss = joint_loss(model(torch.from_numpy(image), torch.from_numpy(context)), torch.from_numpy(y))
            if not torch.isfinite(loss):
                raise ValueError("CNN_NONFINITE_TRAIN_LOSS")
            loss.backward(); optimizer.step()
            total += float(loss.detach())*len(y)
        row = {"epoch": epoch, "train_loss": total/len(train), "seconds": time.perf_counter()-started}
        if validation is not None:
            row["inner_loss"] = _evaluate_loss(model, ds, validation, scaler, batch_size)
            stop = choice.observe(epoch, row["inner_loss"])
        else:
            stop = False
        row["seconds"] = time.perf_counter()-started
        _emit_progress("CNN_EPOCH_COMPLETE", seed, phase, batch_size, **row)
        history.append(row)
        if stop:
            break
    return model, scaler, (choice.best_epoch if validation is not None else epochs), history


def _memory_error(error):
    text = str(error).lower()
    return isinstance(error, MemoryError) or any(x in text for x in ("out of memory", "not enough memory", "can\u0027t allocate memory"))


def _fit_memory_bounded(ds, train, validation, seed, batch_size, epochs=None):
    attempts = []
    while True:
        if attempts:
            gc.collect()  # Previous exception/traceback has now been released.
        try:
            return (*_fit_once(ds, train, validation, seed, batch_size, epochs), batch_size, attempts)
        except (RuntimeError, MemoryError) as error:
            if not _memory_error(error) or batch_size == 1:
                raise
            attempts.append({"failed_batch": batch_size, "reason": str(error), "action": "restart phase from fixed seed; no retained optimizer/weights"})
            batch_size //= 2
            gc.collect()


def predict(model, ds, rows, scaler, batch_size):
    import torch
    result = np.empty((len(rows), 2, 3), dtype=np.float64)
    model.eval()
    offset = 0
    with torch.inference_mode():
        for image, context, _ in batches(ds, rows, scaler, batch_size):
            logits = model(torch.from_numpy(image), torch.from_numpy(context))
            proba = torch.stack((logits[:, :3].softmax(1), logits[:, 3:].softmax(1)), dim=1).numpy()
            result[offset:offset+len(proba)] = proba
            offset += len(proba)
    return result


def _ids(rows):
    return hashlib.sha256("\n".join(r.sample_id for r in rows).encode()).hexdigest()


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1024*1024), b""):
            h.update(part)
    return h.hexdigest()



def write_previews(ds, rows, destination):
    """Three deterministic train-only windows; six unlabeled panels per PNG."""
    selected = sorted({0, len(rows)//2, len(rows)-1})
    items = []
    for i in selected:
        row = rows[i]
        image = render(ds.features[row.row])
        canvas = np.concatenate(list(image), axis=1)
        pixels = (canvas*255).astype(np.uint8)
        def chunk(kind, body):
            return struct.pack(">I", len(body))+kind+body+struct.pack(">I", zlib.crc32(kind+body) & 0xffffffff)
        width, height = pixels.shape[1], pixels.shape[0]
        data = b"".join(b"\x00"+line.tobytes() for line in pixels)
        body = (b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))+
                chunk(b"IDAT", zlib.compress(data))+chunk(b"IEND", b""))
        path = Path(destination)/f"preview-{i}.png"
        path.write_bytes(body)
        items.append({"sample_id": row.sample_id, "decision_ns": row.decision_ns,
                      "path": str(path), "sha256": _sha(path)})
    return items

def _json(path, value):
    path = Path(path); temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2)+"\n")
    temporary.replace(path)


def run(dataset, lock_path, output, fold="validation", batch_size=BATCH_SIZE, memory_reason=None, execute_fit=False):
    """Explicit root gate; this function never opens U or initiates policy search."""
    if not execute_fit:
        raise ValueError("CNN_FIT_REQUIRES_EXPLICIT_ROOT_GO")
    if batch_size not in (1, 2, 4, 8, 16, 32, 64, 128) or batch_size < BATCH_SIZE and not memory_reason:
        raise ValueError("CNN_SMALLER_BATCH_REQUIRES_MEMORY_REASON")
    import torch
    from coinmaster.research.fast_numeric import Dataset, metrics
    torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    ds = Dataset(dataset)
    lock = json.loads(Path(lock_path).read_text())
    if tuple(lock["CNN_seeds"]) != SEEDS or lock["CNN_epoch_max"] != MAX_EPOCHS or lock["CNN_patience"] != PATIENCE:
        raise ValueError("CNN_FROZEN_RECIPE_MISMATCH")
    train, test, inner_train, inner_validation, cutoff, end, inner = partitions(ds.rows, lock, fold)
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    recipe = {"stage": "cnn", "fold": fold, "class_order": CLASS_ORDER,
              "fit_cutoff_ns": cutoff, "prediction_end_ns": end, "inner_cutoff_ns": inner,
              "train_n": len(train), "prediction_n": len(test), "inner_train_n": len(inner_train),
              "inner_validation_n": len(inner_validation), "train_ids_sha256": _ids(train),
              "prediction_ids_sha256": _ids(test), "inner_train_ids_sha256": _ids(inner_train),
              "inner_validation_ids_sha256": _ids(inner_validation), "seeds": SEEDS,
              "epoch_max": MAX_EPOCHS, "patience": PATIENCE, "learning_rate": 1e-5,
              "requested_batch": batch_size, "memory_reason": memory_reason, "renderer": RENDERER,
              "purge": "full horizon_end_ns strictly below fit/inner boundary", "pending_U": "not read or predicted",
              "lock_sha256": _sha(lock_path), "source_sha256": _sha(__file__),
              "dataset_manifest_sha256": _sha(Path(dataset)/"manifest.json")}
    recipe["train_previews"] = write_previews(ds, train, output)
    _json(output/"recipe.json", recipe)
    predictions, runs = [], []
    fit_seconds, inference_seconds = 0., 0.
    for seed in SEEDS:
        t = time.perf_counter()
        model, scaler, best_epoch, selection_history, effective_batch, select_oom = _fit_memory_bounded(
            ds, inner_train, inner_validation, seed, batch_size)
        del model, scaler
        gc.collect()
        model, scaler, _, refit_history, effective_batch, refit_oom = _fit_memory_bounded(
            ds, train, None, seed, effective_batch, best_epoch)
        fit_seconds += time.perf_counter()-t
        path = output/f"seed-{seed}.pt"
        temporary = path.with_suffix(".tmp")
        torch.save({"state_dict": model.state_dict(), "seed": seed, "epochs": best_epoch,
                    "context_mean": scaler.mean.tolist(), "context_scale": scaler.scale.tolist(),
                    "recipe": recipe}, temporary)
        temporary.replace(path)
        t = time.perf_counter()
        proba = predict(model, ds, test, scaler, effective_batch)
        inference_seconds += time.perf_counter()-t
        np.save(output/f"seed-{seed}-probabilities.npy", proba)
        predictions.append(proba)
        runs.append({"seed": seed, "best_checkpoint_epoch": best_epoch, "refit_epochs": len(refit_history),
                     "batch_size": effective_batch, "selection_history": selection_history,
                     "refit_history": refit_history, "memory_retries": select_oom+refit_oom,
                     "checkpoint_sha256": _sha(path)})
        del model, scaler
        gc.collect()
        _json(output/"seed-runs.json", runs)
    averaged = (predictions[0]+predictions[1])/2
    np.save(output/"probabilities.npy", averaged)
    with (output/"predictions.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["sample_id", "decision_ns", "BTC_UP", "BTC_DOWN", "BTC_NONE", "SOL_UP", "SOL_DOWN", "SOL_NONE"])
        for row, proba in zip(test, averaged):
            writer.writerow([row.sample_id, row.decision_ns, *proba.flatten()])
    report = {**recipe, **metrics(test, averaged), "fit_seconds": fit_seconds,
              "inference_seconds": inference_seconds, "seed_runs": runs,
              "model_parameters": PARAMETERS, "model_device": "CPU", "lazy_images": True}
    _json(output/"report.json", report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", required=True); p.add_argument("--lock", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--fold", choices=("oof20", "oof40", "validation"), default="validation")
    p.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    p.add_argument("--memory-reason")
    p.add_argument("--execute-fit", action="store_true")
    args = p.parse_args()
    if not args.execute_fit:
        print(json.dumps({"status": "PLAN_ONLY_NO_DATA_READ_NO_FIT", **vars(args)}))
        return
    report = run(args.dataset, args.lock, args.output, args.fold, args.batch_size, args.memory_reason, True)
    print(json.dumps({k: report[k] for k in ("stage", "fold", "train_n", "prediction_n", "mean_log_loss", "fit_seconds", "inference_seconds")}))


if __name__ == "__main__":
    main()
