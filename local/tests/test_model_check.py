"""Offline acceptance-harness regression through research and encoder boundaries."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from local.model_check import run_scenarios


class Encoder:
    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, texts, batch_size=32):
        return [[1., float(hashlib.sha256(t.encode()).digest()[0]), 2.] for t in texts]


class ModelCheckTests(unittest.TestCase):
    def test_four_scenarios_audit_and_observe_loader_and_changed_text(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_scenarios(Path(directory) / 'acceptance', lambda: Encoder())
            self.assertEqual([s['analysis']['encoded'] for s in result], [3, 0, 1, 0])
            self.assertEqual([s['loader_calls'] for s in result], [1, 0, 1, 0])
            self.assertEqual([s['analysis']['pairs_evaluated'] for s in result], [3, 0, 3, 3])
            self.assertEqual([s['analysis']['stock_pairs'] for s in result], [3, 3, 3, 1])
            self.assertTrue(all(s['audit']['status'] == 'valid' for s in result))
            self.assertEqual(result[2]['changed_vectors'], ['doc:d1'])
            self.assertEqual(result[3]['changed_vectors'], [])
            self.assertTrue(all(s['numeric_excluded'] for s in result))
            with self.assertRaises(FileExistsError):
                run_scenarios(Path(directory) / 'acceptance', lambda: Encoder())
