"""Synthetic tests using stdlib unittest; no market fit or extra test dependencies."""
from types import SimpleNamespace
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
from coinmaster.research.fast_cnn import (render, ContextScaler, batches, EpochChoice,
    partitions, build_model, joint_loss, run, PARAMETERS, write_previews, _emit_progress)


def features(n=1):
    x = np.empty((n, 6, 20, 6), dtype=np.float32)
    x[:] = [.2, .9, .1, .8, 1., .5]
    return x


class RendererProtocolTests(unittest.TestCase):
    def test_renderer_binary_ohlc_volume_and_blank_divider(self):
        image = render(features()[0])
        self.assertEqual(image.shape, (6, 64, 60))
        self.assertEqual(image.dtype, np.float32)
        self.assertEqual(set(np.unique(image)), {0., 1.})
        self.assertFalse(image[:, 48:50].any())
        self.assertTrue(image[0, 5:43, 1].all())
        self.assertEqual(image[0, 38, 0], 1)
        self.assertEqual(image[0, 9, 2], 1)
        self.assertTrue(image[0, 50:64, 1].all())
        self.assertTrue(image[0, 24, 1:59].all())
        x = features()[0]; x[3, :, 4] = 0
        self.assertFalse(render(x)[3, 50:].any())

    def test_renderer_rejects_invalid_shared_features(self):
        for bad in ("shape", "nan", "range", "ohlc"):
            with self.subTest(bad=bad):
                x = features()[0]
                if bad == "shape": x = x[:, :19]
                elif bad == "nan": x[0, 0, 0] = np.nan
                elif bad == "range": x[0, 0, 4] = 2
                else: x[0, 0, 1] = 0
                with self.assertRaises(ValueError): render(x)

    def test_lazy_batches_original_rows_and_train_only_context(self):
        ds = SimpleNamespace(features=features(5), context=np.arange(100).reshape(5, 20))
        rows = [SimpleNamespace(row=i, labels=(i % 3, (i+1) % 3)) for i in (4, 1, 3)]
        scaler = ContextScaler().fit(ds.context[[0, 1]])
        before = scaler.mean.copy()
        actual = list(batches(ds, rows, scaler, 2))
        self.assertEqual([len(x[0]) for x in actual], [2, 1])
        np.testing.assert_array_equal(actual[0][2], [[1, 2], [1, 2]])
        np.testing.assert_allclose(actual[0][1], scaler.transform(ds.context[[4, 1]]))
        np.testing.assert_array_equal(scaler.mean, before)

    def test_epoch_progress_is_flushed_small_json_on_stderr(self):
        import io
        from contextlib import redirect_stderr
        class Stream(io.StringIO):
            flushes = 0
            def flush(self):
                self.flushes += 1
                super().flush()
        stream = Stream()
        with redirect_stderr(stream):
            _emit_progress("CNN_STAGE_START", 7, "inner", 128, timestamp_ns=123)
            _emit_progress("CNN_EPOCH_COMPLETE", 7, "inner", 128,
                           epoch=1, seconds=2.5, train_loss=.8, inner_loss=.9)
        rows = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(stream.flushes, 2)
        self.assertEqual(rows[0]["timestamp_ns"], 123)
        self.assertEqual(rows[1], {"event": "CNN_EPOCH_COMPLETE", "seed": 7,
            "phase": "inner", "batch_size": 128, "epoch": 1, "seconds": 2.5,
            "train_loss": .8, "inner_loss": .9})

    def test_epoch_choice_refits_best_checkpoint_not_patience_tail(self):
        choice = EpochChoice()
        stopped = [choice.observe(i, loss) for i, loss in enumerate([1., .8, .9, 1.], 1)]
        self.assertEqual(choice.best_epoch, 2)
        self.assertEqual(stopped, [False, False, False, True])

    def test_each_inner_and_oof_cutoff_is_purged_without_later_epochs(self):
        from coinmaster.research.fast_numeric import Sample, utc_ns
        hour = 3600*10**9; start = utc_ns("2024-01-01T00:00:00Z")
        fmt = lambda h: np.datetime_as_string(np.datetime64(start+h*hour, "ns"), unit="s")+"Z"
        lock = {"T": [fmt(0), fmt(2000)], "V": [fmt(2000), fmt(2600)],
                "U": [fmt(2600), fmt(3200)], "OOF_fit_cutoffs": [fmt(800), fmt(1400), fmt(2000)],
                "CNN_inner_T_split": fmt(1700)}
        rows = [Sample(i, str(i), start+i*hour, start+(i+72)*hour, start+(i+72)*hour,
                       (0, 1), True, True) for i in range(3000)]
        for fold in ("oof20", "oof40", "validation"):
            train, test, it, iv, cutoff, end, inner = partitions(rows, lock, fold)
            self.assertTrue(all(r.horizon_end_ns < cutoff for r in train))
            self.assertTrue(all(r.horizon_end_ns < inner for r in it))
            self.assertTrue(all(inner <= r.decision_ns and r.horizon_end_ns < cutoff for r in iv))
            self.assertTrue(all(cutoff <= r.decision_ns and r.horizon_end_ns < end for r in test))
            self.assertFalse({r.sample_id for r in train} & {r.sample_id for r in test})
        self.assertEqual(partitions(rows, lock, "oof20")[-1], start+680*hour)

    def test_fit_gate_precedes_any_dataset_or_torch_access(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            with self.assertRaisesRegex(ValueError, "EXPLICIT_ROOT_GO"):
                run(p/"missing", p/"missing-lock", p/"out")
            with self.assertRaisesRegex(ValueError, "MEMORY_REASON"):
                run(p/"missing", p/"missing-lock", p/"out", batch_size=32, execute_fit=True)

    def test_torch_lazy_import_and_cli_plan_never_read_dataset(self):
        script = ("import sys; import coinmaster.research.fast_cnn; "
                  "assert all(x not in sys.modules for x in ('torch','stumpy','aeon'))")
        subprocess.run([sys.executable, "-c", script], check=True)
        p = subprocess.run([sys.executable, "-m", "coinmaster.research.fast_cnn",
            "--dataset", "/missing", "--lock", "/missing", "--output", "/missing"],
            check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(p.stdout)["status"], "PLAN_ONLY_NO_DATA_READ_NO_FIT")

    def test_preview_is_unlabeled_train_only_png(self):
        ds = SimpleNamespace(features=features(4))
        rows = [SimpleNamespace(row=i, sample_id=str(i), decision_ns=i) for i in range(4)]
        with tempfile.TemporaryDirectory() as directory:
            items = write_previews(ds, rows, directory)
            self.assertEqual([r["sample_id"] for r in items], ["0", "2", "3"])
            self.assertTrue(all(Path(r["path"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for r in items))


class ZFixedShapeTests(unittest.TestCase):
    def test_fixed_forward_and_synthetic_backward_no_optimizer_or_weight_update(self):
        import torch
        torch.set_num_threads(1)
        model = build_model().eval()
        self.assertEqual(sum(p.numel() for p in model.parameters()), PARAMETERS)
        x = torch.from_numpy(np.stack([render(features()[0])]))
        context = torch.zeros((1, 20))
        before = model.head[1].weight.detach().clone()
        logits = model(x, context)
        self.assertEqual(list(model.features(x).shape), [1, 256, 3, 60])
        self.assertEqual(list(logits.shape), [1, 6])
        y = torch.tensor([[0, 2]])
        expected = (torch.nn.functional.cross_entropy(logits[:, :3], y[:, 0])+
                    torch.nn.functional.cross_entropy(logits[:, 3:], y[:, 1]))/2
        torch.testing.assert_close(joint_loss(logits, y), expected)
        joint_loss(logits, y).backward()
        self.assertTrue(torch.isfinite(model.head[1].weight.grad).all())
        torch.testing.assert_close(model.head[1].weight.detach(), before)


if __name__ == "__main__":
    unittest.main()
