from concurrent.futures import ThreadPoolExecutor
import hashlib
import base64
import json
from pathlib import Path
import threading
import time
import shutil
import subprocess
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import requests
from scrapers import extension_bridge as bridge
from scrapers import local_browser


class ExtensionBridgeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node needed for extension command tests')
    def test_actual_javascript_commands(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run([shutil.which('node'), 'tests/extension_commands.cjs'], cwd=root, check=True, timeout=20, capture_output=True)

    def test_pairing_origin_auth_and_binary_roundtrip(self):
        connection = bridge.Bridge('test-pairing-key')
        server = ThreadingHTTPServer(('127.0.0.1', 0), bridge.Handler)
        server.daemon_threads = True
        server.bridge = connection
        port = server.server_address[1]
        client = 'test-connector-session'
        url = f'http://127.0.0.1:{port}'
        headers = {'Origin': bridge.ORIGIN, 'Authorization': 'Bearer test-pairing-key'}
        with patch.object(bridge, 'PORT', port):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                self.assertEqual(requests.post(url+'/poll', json={'client': client}, headers={'Origin': bridge.ORIGIN}, timeout=3).status_code, 403)
                self.assertEqual(requests.post(url+'/poll', json={'client': client}, headers={**headers, 'Origin': 'https://evil.example'}, timeout=3).status_code, 403)
                self.assertEqual(requests.post(url+'/poll', json={'client': client}, headers={**headers, 'Host': 'evil.example'}, timeout=3).status_code, 403)
                connection.last_poll = time.monotonic()
                connection.client = client
                with ThreadPoolExecutor(max_workers=1) as pool:
                    result = pool.submit(connection.invoke, 'fetch_asset', 'https://www.eauctionsindia.com/storage/images/test.webp')
                    response = requests.post(url+'/poll', json={'client': client}, headers=headers, timeout=3)
                    job = response.json()['command']
                    self.assertEqual(job['method'], 'fetch_asset')
                    response = requests.post(url+'/result', json={'client': client, 'id': job['id'], 'result': {'status': 200, 'type': 'image/webp', 'data': 'AP9iaW5hcnk='}}, headers=headers, timeout=3)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(result.result(timeout=3)['data'], 'AP9iaW5hcnk=')
                with self.assertRaises(ValueError):
                    connection.poll('different-connector-session')
                with self.assertRaises(ValueError):
                    connection.invoke('evaluate', 'arbitrary JS')
            finally:
                server.shutdown()
                server.server_close()

    def test_extension_avoids_debugging_endpoint_and_uses_same_export_session(self):
        from unittest.mock import Mock
        connection = Mock()
        connection.invoke.side_effect = [None, None, {'status': 200, 'type': 'image/webp', 'data': 'AP9iaW5hcnk='}]
        with patch.object(bridge, 'connected_bridge', return_value=connection), patch.object(local_browser, 'chrome_endpoint') as endpoint:
            with local_browser.desktop_browser(None, 'https://www.eauctionsindia.com') as page:
                self.assertIs(page.session, connection)
                with self.assertRaises(ValueError):
                    page.goto('https://example.com/')
            response = local_browser.fetch_chrome_attachment('https://www.eauctionsindia.com/storage/images/test.webp')
            self.assertEqual(response.content, b'\x00\xffbinary')
            endpoint.assert_not_called()

    def test_manifest_identity_matches_allowed_origin(self):
        folder = Path(__file__).resolve().parents[1] / 'browser_extension'
        manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        digest = hashlib.sha256(base64.b64decode(manifest['key'])).hexdigest()[:32]
        extension_id = ''.join(chr(97+int(char, 16)) for char in digest)
        self.assertEqual(bridge.ORIGIN, 'chrome-extension://' + extension_id)
        self.assertEqual(manifest['minimum_chrome_version'], '96')
        self.assertNotIn('cookies', manifest['permissions'])
        self.assertNotIn('<all_urls>', manifest['host_permissions'])
        self.assertTrue((folder/'connector.js').is_file())


if __name__ == '__main__':
    unittest.main()
