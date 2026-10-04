import csv
import json
import tempfile
import unittest
from pathlib import Path
import sys
import uuid
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import process_json as processor


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write_csv(self, text):
        path = self.work / 'input.csv'
        path.write_text(text, encoding='utf-8')
        return path

    def test_json_nested_mapping_dedupe_required_zero_unicode(self):
        payload = processor.load_json(ROOT / 'examples/response.json')
        fields = [('id', 'id'), ('name', 'profile.name'), ('city', 'profile.city'), ('total', 'stats.total')]
        report = processor.process(payload, self.work / 'out', fields, 'data.items', ['id'], ['id'])
        self.assertEqual((report['input_records'], report['exported_records']), (6, 4))
        self.assertEqual(report['duplicate_record_indexes'], [3])
        self.assertEqual(report['rejected_records'][0]['record'], 4)
        with (self.work / 'out/data.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[1]['total'], '0')
        self.assertEqual(rows[1]['city'], '')
        self.assertEqual(rows[2]['name'], 'اسم تجريبي')
        self.assertEqual(rows[3]['name'], "'=2+2")

    def test_json_bad_array_path_rejected(self):
        with self.assertRaises(ValueError):
            processor.process({}, self.work / 'out', [('id', 'id')], 'data.items')

    def test_json_duplicate_output_header_rejected(self):
        with self.assertRaises(ValueError):
            processor.process([], self.work / 'out', [('id', 'id'), ('id', 'name')])

    def test_json_malformed_input_rejected(self):
        source = self.work / 'bad.json'
        source.write_text('{broken')
        with self.assertRaises(json.JSONDecodeError):
            processor.load_json(source)

    def test_json_limit_and_credential_url_rejected(self):
        source = self.work / 'large.json'
        source.write_bytes(b' ' * (processor.MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            processor.load_json(source)
        with self.assertRaises(ValueError):
            processor.load_json(url=f'https://{uuid.uuid4().hex}:{uuid.uuid4().hex}@example.invalid/data')

    def test_json_existing_output_is_preserved(self):
        self.work.joinpath('out').mkdir()
        with self.assertRaises(ValueError):
            processor.process([], self.work / 'out', [('id', 'id')])

    def test_json_reads_real_local_http_and_rejects_redirect(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', '/data')
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'[{"id":"local-api"}]')
            def log_message(self, *_):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}'
            self.assertEqual(processor.load_json(url=url + '/data'), [{'id': 'local-api'}])
            with self.assertRaises(ValueError):
                processor.load_json(url=url + '/redirect')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
