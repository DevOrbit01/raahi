"""Authenticated loopback bridge for the user's normal Chrome extension.

Only fixed auction-tab operations are supported. Browser cookies remain in
Chrome. The pairing key is local app data and is never included in a release.
"""
import atexit
from concurrent.futures import Future
from contextlib import contextmanager
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import secrets
import shutil
import sys
import threading
import time
from types import SimpleNamespace
from app_paths import application_data_dir

PORT = 49381
ORIGIN = 'chrome-extension://jcnpgoaohkejekofgopddmefglmnjkgg'
MAX_BODY = 64 * 1024 * 1024
_bridge = None
_lock = threading.Lock()


class Bridge:
    def __init__(self, key):
        self.key = key
        self.commands = queue.Queue()
        self.pending = {}
        self.lock = threading.Lock()
        self.last_poll = 0
        self.client = None

    def connected(self):
        return time.monotonic() - self.last_poll < 15

    def invoke(self, method, *args, **kwargs):
        if method == 'ensure':
            if not self.connected():
                raise RuntimeError('Open the Raahi Connector extension tab and click Connect. Keep that tab open.')
            return
        if method == 'wait_for_timeout':
            time.sleep(args[0] / 1000)
            return
        if method in ('disconnect', 'stop'):
            return  # Keep the user's Chrome/tabs open.
        self.invoke('ensure')
        if method not in ('goto', 'content', 'bring_to_front', 'is_closed', 'fetch_asset'):
            raise ValueError('Unsupported browser operation')
        job_id = secrets.token_hex(16)
        future = Future()
        with self.lock:
            self.pending[job_id] = future
        self.commands.put({'id': job_id, 'method': method, 'args': args})
        try:
            result = future.result(timeout=90)
            return SimpleNamespace(status=result['status']) if method == 'goto' else result
        finally:
            with self.lock:
                self.pending.pop(job_id, None)

    def poll(self, client):
        with self.lock:
            if self.connected() and self.client != client:
                raise ValueError('Another connector tab is already connected. Close it first.')
            self.client = client
            self.last_poll = time.monotonic()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                command = self.commands.get(timeout=max(.01, deadline - time.monotonic()))
            except queue.Empty:
                return None
            with self.lock:
                if command['id'] in self.pending:
                    return command
        return None

    def resolve(self, data, client):
        with self.lock:
            if client != self.client:
                raise ValueError('Connector session changed')
            self.last_poll = time.monotonic()
            future = self.pending.get(data.get('id'))
            if future is not None and not future.done():
                if data.get('error'):
                    future.set_exception(RuntimeError(str(data['error'])[:500]))
                else:
                    future.set_result(data.get('result'))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log pairing keys, browser data, or URLs.

    def allowed(self):
        return self.headers.get('Origin') == ORIGIN and self.headers.get('Host') == f'127.0.0.1:{PORT}'

    def reply(self, status, data):
        content = json.dumps(data).encode('utf-8')
        self.send_response(status)
        if self.allowed():
            self.send_header('Access-Control-Allow-Origin', ORIGIN)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_OPTIONS(self):
        if not self.allowed():
            self.reply(403, {'error': 'Origin denied'})
            return
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', ORIGIN)
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_POST(self):
        bridge = self.server.bridge
        if not self.allowed() or not hmac.compare_digest(
            self.headers.get('Authorization', ''), 'Bearer ' + bridge.key
        ):
            self.reply(403, {'error': 'Pairing denied'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > MAX_BODY:
                raise ValueError('Invalid message size')
            self.connection.settimeout(30)
            data = json.loads(self.rfile.read(length))
            client = data.get('client')
            if not isinstance(client, str) or not 16 <= len(client) <= 64:
                raise ValueError('Invalid connector session')
            if self.path == '/poll':
                self.reply(200, {'command': bridge.poll(client)})
            elif self.path == '/result':
                bridge.resolve(data, client)
                self.reply(200, {'ok': True})
            else:
                self.reply(404, {'error': 'Unknown operation'})
        except (ValueError, TypeError, OSError):
            self.reply(400, {'error': 'Invalid connector message or duplicate connector tab'})


def start_bridge():
    global _bridge
    with _lock:
        if _bridge is not None:
            return _bridge
        folder = Path(application_data_dir())
        folder.mkdir(parents=True, exist_ok=True)
        key_path = folder / 'browser-connector.key'
        try:
            key = key_path.read_text(encoding='utf-8').strip()
        except FileNotFoundError:
            key = secrets.token_urlsafe(32)
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(key)
        if len(key) != 43 or not all(char.isalnum() or char in '-_' for char in key):
            raise RuntimeError('Invalid local connector pairing file. Contact support to reset browser pairing.')
        bridge = Bridge(key)
        try:
            server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
        except OSError as exc:
            raise RuntimeError('Raahi browser connector port is in use. Close other Raahi app instances and retry.') from exc
        server.daemon_threads = True
        server.bridge = bridge
        bridge.server = server
        threading.Thread(target=server.serve_forever, name='Raahi extension bridge', daemon=True).start()
        _bridge = bridge
        return bridge


def connected_bridge():
    return _bridge if _bridge is not None and _bridge.connected() else None


def prepare_extension():
    bridge = start_bridge()
    source = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'browser_extension'
    target = Path(application_data_dir()) / 'ChromeExtension'
    shutil.copytree(source, target, dirs_exist_ok=True)
    return target, bridge.key


def _stop():
    if _bridge is not None:
        _bridge.server.shutdown()


atexit.register(_stop)
