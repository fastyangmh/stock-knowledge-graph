import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from local.market_prices import normalize, store, source_info
from local.market_graph import read_prices, attach_prices
from local.core import connect, init_db, import_payload
from local.export_json import export
from local.validate_release import validate_data_dir

CSV='日期,證券代號,證券名稱,開盤價,最高價,最低價,收盤價,成交股數,成交金額,成交筆數\n20200102,1000,Synthetic,10.00,12.00,9.00,11.00,1000,11000,20\n'.encode()
DAY='2020-01-02';OBS='2020-01-02T09:00:00+00:00';LATER='2020-01-03T09:00:00+00:00'

class MarketGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.db=self.root/'prices.db'
        self.payload=normalize(CSV,'twse',['1000'],DAY,OBS)
        self.save(self.payload)
    def save(self,p):
        with sqlite3.connect(self.db) as conn:store(conn,p,'local_file_unverified')
    def read(self,known=LATER):return read_prices(self.db,'twse',['1000'],DAY,known)
    def test_cutoff_and_revisions(self):
        newer=normalize(CSV.replace(b'11.00,1000',b'11.50,1000'),'twse',['1000'],DAY,LATER);self.save(newer)
        self.assertEqual(self.read(OBS)[0]['record']['close'],'11.00')
        self.assertEqual(self.read()[0]['record']['close'],'11.50')
        with self.assertRaisesRegex(ValueError,'coverage'):self.read('2020-01-02T08:00:00Z')
    def test_read_only_does_not_create_or_change_database(self):
        before=self.db.read_bytes();self.read();self.assertEqual(self.db.read_bytes(),before)
        missing=self.root/'missing.db'
        with self.assertRaises(ValueError):read_prices(missing,'twse',['1000'],DAY,LATER)
        self.assertFalse(missing.exists())
    def test_attach_creates_numeric_node_not_embedding_document(self):
        with connect(self.root/'graph.db') as conn:
            init_db(conn);import_payload(conn,{'stocks':[{'stock_id':'TW:1000','ticker':'1000','market':'TW','name':'Synthetic'}]})
            self.assertEqual(attach_prices(conn,self.read()),1)
            self.assertEqual(conn.execute('SELECT count(*) FROM documents').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT count(*) FROM embeddings').fetchone()[0],0)
            export(conn,self.root/'out',lifecycle=True)
            self.assertEqual(validate_data_dir(self.root/'out'),1)
            graph=json.loads((self.root/'out/stocks/1000/graph.json').read_text())
            market=next(n for n in graph['nodes'] if n['type']=='market_price')
            self.assertEqual(market['close'],'11.00');self.assertEqual(market['volume_shares'],1000)
            self.assertEqual(graph['edges'][0]['relation'],'has_market_price');self.assertIsNone(graph['edges'][0]['score'])
    def test_missing_stock_rejected(self):
        with connect(self.root/'graph.db') as conn:
            init_db(conn)
            with self.assertRaisesRegex(ValueError,'absent'):attach_prices(conn,self.read())
    def test_tampered_count_and_price_types_rejected(self):
        for key,value in (('close',11.0),('volume_shares',True),('close','999.00'),('price_basis','adjusted')):
            with self.subTest(key=key):
                record=copy.deepcopy(self.payload['records'][0]);record[key]=value
                with sqlite3.connect(self.db) as conn:conn.execute('UPDATE market_price_observations SET record_json=?',(json.dumps(record),))
                with self.assertRaises(ValueError):self.read()
    def test_tampered_source_and_checksum_rejected(self):
        with sqlite3.connect(self.db) as conn:conn.execute("UPDATE market_price_observations SET raw_sha256='invalid'")
        with self.assertRaises(ValueError):self.read()
    def test_symlink_rejected(self):
        link=self.root/'link.db';link.symlink_to(self.db)
        with self.assertRaises(ValueError):read_prices(link,'twse',['1000'],DAY,LATER)
    def test_wrong_market_not_silently_substituted(self):
        with self.assertRaisesRegex(ValueError,'coverage'):read_prices(self.db,'tpex',['1000'],DAY,LATER)
