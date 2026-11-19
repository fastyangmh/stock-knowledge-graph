"""Offline capacity diagnostics through the research and benchmark interfaces."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from local.model_check import fixture
from local.research import run
from local.tests.test_model_check import Encoder


class CapacityTests(unittest.TestCase):
    def test_research_reports_only_work_performed_in_this_run(self):
        ticks = [0.]

        class TimedEncoder(Encoder):
            def encode(self, texts, batch_size):
                ticks[0] += 3
                return super().encode(texts, batch_size)

        def load(name, revision):
            ticks[0] += 7
            return TimedEncoder()

        with TemporaryDirectory() as directory, patch('time.perf_counter', lambda: ticks[0]):
            root = Path(directory)
            source = root / 'input.json'
            source.write_text(json.dumps(fixture()))
            options = dict(history_db=root / 'ledger.db', output_root=root / 'runs',
                           analysis='semantic', revision='test', encoder_loader=load)
            cold = run(source, ['1000', '1001', '1002'], **options)['analysis']
            hot = run(source, ['1000', '1001', '1002'], **options)['analysis']
            self.assertEqual((cold['model_load_seconds'], cold['encode_seconds']), (7, 3))
            self.assertGreaterEqual(cold['pair_cpu_seconds'], 0)
            self.assertEqual((hot['model_load_seconds'], hot['encode_seconds'], hot['pair_cpu_seconds']), (0, 0, 0))

    def test_full_sort_verifier_detects_missing_extra_and_wrong_score(self):
        from local.capacity_benchmark import compare_exact
        import numpy as np

        # A and C are orthogonal. B lies halfway between them; A wins its tie.
        vectors = np.array([[1., 0.], [1., 1.], [0., 1.]])
        observed = {('A', 'B'): .70, ('A', 'C'): .25}
        result = compare_exact(['A', 'B', 'C'], vectors, observed, top_k=1, threshold=.1)
        self.assertEqual((result['expected_pairs'], result['missing_pairs'], result['extra_pairs']), (2, 1, 1))
        self.assertEqual(result['recall'], .5)
        self.assertAlmostEqual(result['max_absolute_score_error'], 2**-.5 - .70)
        self.assertFalse(result['passed'])

    def test_benchmark_refuses_any_overbudget_size_before_model_io_or_output(self):
        from local.capacity_benchmark import main

        with TemporaryDirectory() as directory:
            output = Path(directory) / 'new-results'
            with self.assertRaisesRegex(ValueError, '6 candidate pairs exceed budget 3'):
                main(['--sizes', '3', '4', '--max-pairs', '3', '--output', str(output),
                      '--model-cache', str(Path(directory) / 'absent')])
            self.assertFalse(output.exists())

    def test_saved_workload_and_phase_measurements_reproduce_cold_and_hot_search(self):
        from local.capacity_benchmark import write_workload, measure_phase, verify_phase

        with TemporaryDirectory() as directory:
            root = Path(directory)
            checksum = write_workload(root / 'input.json', 12, 20261119)
            self.assertEqual(write_workload(root / 'repeat.json', 12, 20261119), checksum)
            for mode, encoded, hits, pairs in [('cold', 12, 0, 66), ('hot', 0, 12, 0)]:
                row = measure_phase(root, max_pairs=66, encoder_loader=lambda *args: Encoder())
                exact = verify_phase(root, row, size=12, mode=mode)
                self.assertEqual((row['analysis']['encoded'], row['analysis']['cache_hits'],
                                  row['analysis']['pairs_evaluated']), (encoded, hits, pairs))
                self.assertEqual(exact['recall'], 1.)
                self.assertTrue(exact['passed'])
                self.assertGreater(row['peak_rss_bytes'], 0)
                self.assertGreater(row['bundle_json_bytes'], row['display_json_bytes'])

    def test_cli_requires_new_private_destination_and_verified_offline_weights(self):
        from local.capacity_benchmark import main

        with TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / 'previous'
            old.mkdir()
            sentinel = old / 'latest.json'
            sentinel.write_bytes(b'preserve')
            options = ['--sizes', '3', '--model-cache', str(root / 'missing-cache'), '--output']
            with self.assertRaises(FileExistsError):
                main([*options, str(old)])
            self.assertEqual(sentinel.read_bytes(), b'preserve')
            with self.assertRaises(FileNotFoundError):
                main([*options, str(root / 'new')])

    def test_invalid_vector_cannot_pass_as_an_empty_baseline(self):
        from local.capacity_benchmark import compare_exact

        with self.assertRaisesRegex(ValueError, 'invalid baseline'):
            compare_exact(['A', 'B'], [[0., 0.], [1., 0.]], {}, top_k=1, threshold=1.)
