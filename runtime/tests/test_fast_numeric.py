"""Synthetic-only focused checks; no market file or transformer training."""
import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np

from coinmaster.research.fast_numeric import (
    Sample, Heads, admissible_analog, fit_scale, independent, load_samples,
    metrics, partition, prior, raw_channels, select_recognizer, smooth_analogs,
    transformed, Dataset, historical_continuation, scaled_training_memmap,
)


def sample(i, t, h=None, selected=True):
    return Sample(i, str(i), t, t+72 if h is None else h, t+30, (i%3, (i+1)%3),
                  selected, True)


class NumericTests(unittest.TestCase):
    def test_strict_full_horizon_purge_not_early_touch(self):
        rows = [sample(0, 0, 100), sample(1, 1, 99), sample(2, 100, 199),
                sample(3, 101, 200)]
        train, test = partition(rows, 0, 100, 200)
        self.assertEqual([r.row for r in train], [1])
        self.assertEqual([r.row for r in test], [2])

    def test_train_scale_unchanged_by_future_and_common_price_scale(self):
        values = np.ones((50, 6))
        close = np.exp(np.cumsum(np.sin(np.arange(50))*.01))
        values[:, [0,1,2,3,5]] = close[:, None]
        values[:, 4] = np.arange(50)+1
        ts = np.arange(50)
        before = fit_scale(ts, values, 1, 30)
        changed = values.copy()
        changed[30:] *= 9999
        self.assertEqual(before, fit_scale(ts, changed, 1, 30))
        channels = raw_channels(values, *before)
        np.testing.assert_allclose(channels[0, 1:], channels[5, 1:])
        self.assertTrue(np.isnan(channels[:, 0]).all())

    def test_age_readiness_full_horizon_and_near_copy(self):
        old = sample(0, 400, 472)
        self.assertTrue(admissible_analog(old, 600, 396, 4, 100))
        self.assertFalse(admissible_analog(old, 600, 396, 0, 100))
        self.assertFalse(admissible_analog(old, 450, 446, 4, 10))
        self.assertFalse(admissible_analog(old, 480, 396, 4, 100))

    def test_independence_and_three_pseudocount_fallback(self):
        c = [(2., 10, "x"), (1., 11, "y"), (3., 30, "z")]
        self.assertEqual([x[2] for x in independent(c, 20)], ["y"])
        pi = np.array([[.2,.3,.5], [.5,.4,.1]])
        np.testing.assert_array_equal(smooth_analogs([(0,1)]*2, pi), pi)
        got = smooth_analogs([(0,1)]*3, pi)
        np.testing.assert_allclose(got, (np.array([[3,0,0],[0,3,0]])+3*pi)/6)

    def test_U_labels_not_parsed_and_original_offsets_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"samples.csv"
            fields = ["sample_id","decision_ns","split","selected_train","feature_valid",
                      "joint_eligible","btc_label","sol_label","btc_ready_ns","sol_ready_ns",
                      "horizon_end_ns"]
            with p.open("w",newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
                w.writerow(dict(zip(fields, ["A","1","T","1","1","1","0","2","2","3","73"])))
                w.writerow(dict(zip(fields, ["U","2","U","0","1","1","DO_NOT_PARSE",
                                             "DO_NOT_PARSE","INVALID","INVALID","INVALID"])))
            rows = load_samples(p)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].row, 0)

    def test_chunked_transform_preserves_channel_order_and_context(self):
        class Data:
            context = np.arange(80,dtype=np.float32).reshape(4,20)
            def tensor(self, rows, tf):
                return np.array([np.full((12,20),r.row+tf) for r in rows])
        class Transform:
            def transform(self, x):
                return x[:,0,:2]
        rows = [sample(i,i) for i in range(4)]
        with tempfile.TemporaryDirectory() as tmp:
            z, widths = transformed(Data(), rows, [Transform()]*3,
                                     Path(tmp)/"z.npy", chunk=2)
            self.assertEqual(widths,[2,2,2])
            np.testing.assert_array_equal(z[3,:6], [3,3,4,4,5,5])
            np.testing.assert_array_equal(z[:,6:],Data.context)

    def test_metrics_and_complete_selection_gate(self):
        rows = [sample(i,i*100) for i in range(6)]
        p = np.full((6,2,3),1/3)
        m = metrics(rows,p)
        self.assertAlmostEqual(m["mean_log_loss"],np.log(3))
        self.assertAlmostEqual(m["BTC"]["brier_sum_classes"],2/3)
        self.assertEqual(select_recognizer({})["status"],"PENDING_ALL_FOUR_AND_CONTROLS")


    def test_raw_continuation_strict_bounds_and_single_panel_cache(self):
        from unittest.mock import patch
        step = 3600*10**9
        ts = np.arange(25,dtype=np.int64)*step
        raw = np.ones((25,6),dtype=np.float64)
        raw[:,3] = 1000+3*np.arange(25)
        sol = raw.copy(); sol[:,3] = 10+np.arange(25)
        arrays = {f"p{p}_available_ns": ts for p in range(6)}
        arrays.update({f"p{p}_values": raw if p%2==0 else sol for p in range(6)})
        class Archive:
            reads = 0
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def __getitem__(self,key):
                self.reads += 1
                return arrays[key].copy()
        archive = Archive()
        ds = Dataset.__new__(Dataset)
        ds.path = Path("/synthetic")
        ds._panels = None
        with patch("coinmaster.research.fast_numeric.np.load",return_value=archive) as load:
            first = ds.panel(0)
            self.assertIs(first,ds.panel(0))
            self.assertIs(first[1],ds.panel(0)[1])
            self.assertEqual(load.call_count,1)
            self.assertEqual(archive.reads,12)
            occurrence = {"available_end_ns": int(ts[20])}
            sample_data = {"sample_id":"real-price-fixture","decision_ns":int(ts[20]),
                           "horizon_end_ns":int(ts[22])}
            result = historical_continuation(ds,0,occurrence,sample_data)
        btc = result["assets"]["BTC"]
        self.assertEqual(btc["future_available_ns"],[int(ts[21]),int(ts[22])])
        self.assertEqual(btc["future_raw_close"],[1063.,1066.])
        self.assertEqual(btc["input_raw_OHLCV_MA20"][-1][3],1060.)
        self.assertEqual(result["assets"]["SOL"]["future_raw_close"],[31.,32.])


    def test_chunk_scaler_float32_rounding_and_float64_head_equivalence(self):
        from sklearn.preprocessing import StandardScaler
        from sklearn.utils.validation import check_array
        rng = np.random.default_rng(7)
        raw = rng.normal(size=(96,45)).astype(np.float32)
        raw[:,0] = 1; raw[:,1] = 0
        y = rng.integers(0,3,size=(96,2))
        query = rng.normal(size=(17,45)).astype(np.float32)
        expected_scaler = StandardScaler(copy=False)
        expected = expected_scaler.fit_transform(raw.copy())
        baseline = Heads().fit(raw.copy(),y)
        with tempfile.TemporaryDirectory() as tmp:
            scaler = StandardScaler(copy=False)
            scaled = scaled_training_memmap(scaler, raw, Path(tmp)/"scaled.npy", chunk=13)
            self.assertEqual(scaled.dtype,np.float64)
            self.assertTrue(scaled.flags.c_contiguous)
            validated = check_array(scaled,dtype=np.float64,order="C",copy=False)
            self.assertTrue(np.shares_memory(scaled,validated))
            np.testing.assert_allclose(scaler.mean_,expected_scaler.mean_,rtol=1e-12,atol=1e-12)
            np.testing.assert_allclose(scaler.var_,expected_scaler.var_,rtol=1e-12,atol=1e-12)
            np.testing.assert_allclose(scaled,expected.astype(np.float64),rtol=1e-6,atol=2e-7)
            value_drift = float(np.abs(scaled-expected).max())
            mean_drift = float(np.abs(scaler.mean_-expected_scaler.mean_).max())
            var_drift = float(np.abs(scaler.var_-expected_scaler.var_).max())
            del validated
            scaled._mmap.close()
            mapped = np.lib.format.open_memmap(Path(tmp)/"raw.npy",mode="w+",
                                              dtype=np.float32,shape=raw.shape)
            mapped[:] = raw; mapped.flush()
            corrected = Heads().fit(mapped,y,workspace=Path(tmp)/"heads.npy",
                                    chunk=13,consume_input=True)
            self.assertTrue(mapped._mmap.closed)
            actual_proba = corrected.predict(query.copy())
            baseline_proba = baseline.predict(query.copy())
            np.testing.assert_allclose(actual_proba,baseline_proba,rtol=1e-6,atol=2e-7)
            print("MEMORY_ONLY_EQUIVALENCE",{
                "mean_max_abs":mean_drift,"variance_max_abs":var_drift,
                "standardized_f32_max_abs":value_drift,
                "proba_max_abs":float(np.abs(actual_proba-baseline_proba).max()),
                "C_float64_validation_shares_memory":True})

    def test_heads_are_train_only_and_restore_missing_class_order(self):
        # Tiny actual fixed logistic API fit; no aeon/STUMPY compilation or market inputs.
        x = np.array([[0,1],[1,0],[2,1],[3,0],[4,1],[5,0]],np.float32)
        y = np.array([[0,2],[2,2],[0,2],[2,2],[0,2],[2,2]])
        head = Heads().fit(x.copy(),y)
        mean = head.scaler.mean_.copy()
        p = head.predict(np.array([[100,100]],np.float32))
        np.testing.assert_array_equal(head.scaler.mean_, mean)
        self.assertEqual(p.shape,(1,2,3))
        self.assertEqual(p[0,0,1],0)
        np.testing.assert_array_equal(p[0,1], [0,0,1])
        np.testing.assert_allclose(p.sum(axis=2),1)


if __name__ == "__main__":
    unittest.main()
