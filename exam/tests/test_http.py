"""Handler: Origin / Content-Type rejection and malformed bodies, over a real socket."""
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

import tests._path  # noqa: F401
import server
from store import Results, SessionFile
from tests.test_exam import Clock, FakeCluster


class HttpCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        server.EXAM = server.Exam(Results(d / "r.json"), SessionFile(d / "s.json"), now=Clock(),
                                  cluster=FakeCluster(), do_reset=False)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def req(self, method, path, body=None, headers=None, raw=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": f"localhost:{self.port}"}
        h.update(headers or {})
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        c.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for k, v in h.items():
            c.putheader(k, v)
        if data is not None and "Content-Length" not in h:
            c.putheader("Content-Length", str(len(data)))
        c.endheaders(data)
        r = c.getresponse()
        out = r.read()
        c.close()
        try:
            return r.status, json.loads(out)
        except ValueError:
            return r.status, out

    def post(self, path, body=None, ctype="application/json", origin=None, **kw):
        h = {"Content-Type": ctype}
        if origin:
            h["Origin"] = origin
        h.update(kw.pop("headers", {}))
        return self.req("POST", path, body, h, **kw)

    def own(self, host="localhost"):
        return f"http://{host}:{self.port}"

    # ---- Origin
    def test_own_origin_is_accepted(self):
        for host in ("localhost", "127.0.0.1"):
            self.assertEqual(self.post("/api/session/end", {}, origin=self.own(host))[0], 400)   # past the gate: no session yet

    def test_other_localhost_port_is_rejected(self):
        self.assertEqual(self.post("/api/session/end", {}, origin="http://localhost:9999")[0], 403)

    def test_foreign_origin_is_rejected(self):
        self.assertEqual(self.post("/api/session/end", {}, origin="http://evil.example")[0], 403)
        self.assertEqual(self.post("/api/session/end", {}, origin="http://localhost.evil.example:%d" % self.port)[0], 403)

    def test_get_with_foreign_origin_is_rejected(self):
        self.assertEqual(self.req("GET", "/api/state", headers={"Origin": "http://localhost:9999"})[0], 403)

    def test_bad_host_header_is_rejected(self):
        self.assertEqual(self.req("GET", "/api/state", headers={"Host": "evil.example"})[0], 403)

    # ---- Content-Type
    def test_content_type_must_be_json_exactly(self):
        for ct in ("text/plain", "application/jsonx", "x/application/json", "application/json-seq", ""):
            self.assertEqual(self.post("/api/session/end", {}, ctype=ct)[0], 415, ct)

    def test_json_with_charset_or_other_case_is_accepted(self):
        for ct in ("application/json; charset=utf-8", "Application/JSON"):
            self.assertEqual(self.post("/api/session/end", {}, ctype=ct)[0], 400, ct)    # passes the gate

    # ---- malformed bodies
    def test_non_object_json_is_400(self):
        for raw in (b"[]", b"3", b'"x"', b"null", b"{bad"):
            code, _ = self.post("/api/task/open", raw=raw)
            self.assertEqual(code, 400, raw)

    def test_bad_content_length(self):
        self.assertEqual(self.post("/api/session/end", raw=b"{}", headers={"Content-Length": "-5"})[0], 400)
        self.assertEqual(self.post("/api/session/end", raw=b"{}", headers={"Content-Length": "abc"})[0], 400)
        self.assertEqual(self.post("/api/session/end", raw=b"{}", headers={"Content-Length": str(10 ** 9)})[0], 413)

    def test_unknown_task_id_types(self):
        for tid in (None, 5, ["t01"], {"a": 1}):
            code, _ = self.post("/api/task/open", {"id": tid})
            self.assertIn(code, (400, 404), tid)

    def test_get_failure_is_json_500_not_a_dropped_connection(self):
        orig = server.EXAM.state
        server.EXAM.state = lambda: 1 / 0
        try:
            code, body = self.req("GET", "/api/state")
        finally:
            server.EXAM.state = orig
        self.assertEqual(code, 500)
        self.assertIn("error", body)


if __name__ == "__main__":
    unittest.main()
