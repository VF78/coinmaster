"""Unchanged durable-CAS assertions extracted from uncollectable archived actor suite."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import sqlite3
import unittest
from coinmaster.strategy.cm2_checkpoint import NativeCheckpointStore,KEY,canonical

class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.store=NativeCheckpointStore(NS(db=self.db))

    def tearDown(self): self.db.close()

    def test_cas_idempotent_and_conflict(self):
        self.assertEqual(self.store.persist(b'one',0),1)
        changes=self.db.total_changes
        self.assertEqual(self.store.persist(b'one',1),1)
        self.assertEqual(self.db.total_changes,changes)
        self.assertIsNone(self.store.persist(b'two',0))
        self.assertEqual(self.store.read(),(1,b'one'))
        self.assertEqual(self.store.persist(b'two',1),2)

    def test_integrity_and_foreign_transaction_fail_closed(self):
        self.store.persist(b'one',0)
        self.db.execute('UPDATE cm2_domain_checkpoint SET body=?',(b'corrupt',));self.db.commit()
        with self.assertRaisesRegex(ValueError,'INTEGRITY'): self.store.read()
        self.db.execute('BEGIN')
        with self.assertRaisesRegex(ValueError,'FOREIGN_TRANSACTION'): self.store.persist(b'two',1)
        self.db.rollback()

    def test_durable_reopen_same_bytes(self):
        with TemporaryDirectory() as path:
            connection=sqlite3.connect(Path(path)/'native.sqlite')
            store=NativeCheckpointStore(NS(db=connection));store.persist(b'proof',0);connection.close()
            connection=sqlite3.connect(Path(path)/'native.sqlite')
            self.assertEqual(NativeCheckpointStore(NS(db=connection)).read(),(1,b'proof'));connection.close()
