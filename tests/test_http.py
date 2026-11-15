from contextlib import contextmanager
import http.client
import json
import re
import threading

import pytest

from incident_rehearsal.engine import RehearsalError
from incident_rehearsal.server import create_server


@contextmanager
def running():
    with create_server("kafka-lag") as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(timeout=5)


def request(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    content = response.read()
    result = (response.status, dict(response.getheaders()), content)
    connection.close()
    return result


def authorized(server):
    status, headers, html = request(server, "GET", "/")
    assert status == 200
    token = re.search(rb'const token="([^"]+)"', html).group(1).decode()
    return {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{server.server_port}",
            "X-Rehearsal-Token": token}


def post(server, path, data, headers):
    status, _, body = request(server, "POST", path, json.dumps(data), headers)
    return status, json.loads(body)


def test_ui_and_api_hide_unreleased_evidence_and_have_security_headers():
    with running() as server:
        status, headers, body = request(server, "GET", "/")
        assert status == 200
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert headers["Cache-Control"] == "no-store"
        assert "rollback-verified" not in body.decode()
        status, _, body = request(server, "GET", "/api/state")
        assert status == 200 and b"rollback-verified" not in body
        headers = authorized(server)
        status, data = post(server, "/api/decide", {"action_id": "declare-recovery",
                         "evidence_ids": ["rollback-verified"], "rationale": "I guessed a future ID."}, headers)
        assert status == 400 and "unreleased" in data["error"]


def test_mutations_require_both_same_origin_and_token():
    with running() as server:
        good = authorized(server)
        for headers in ({}, {**good, "Origin": "https://evil.example"},
                        {**good, "X-Rehearsal-Token": "wrong"}):
            assert post(server, "/api/advance", {"minutes": 1}, headers)[0] == 403
        assert post(server, "/api/advance", {"minutes": 1}, good)[0] == 200


def test_request_and_lifecycle_boundaries():
    with running() as server:
        headers = authorized(server)
        for path in ("/../engine.py", "/%2e%2e/engine.py", "/api/state?all=true", "/scenarios/kafka-lag.json"):
            assert request(server, "GET", path)[0] == 404
        assert request(server, "GET", "/api/state", headers={"Host": "evil.example"})[0] == 421
        assert request(server, "GET", "/api/export")[0] == 409
        assert request(server, "POST", "/api/advance", "{}", {**headers, "Content-Type": "text/plain"})[0] == 415
        assert request(server, "POST", "/api/advance", "x" * 16_385, headers)[0] == 413
        assert request(server, "POST", "/api/advance", "{", headers)[0] == 400
        assert post(server, "/api/advance", {"minutes": True}, headers)[0] == 400
        assert post(server, "/api/decide", {"action_id": "unknown"}, headers)[0] == 400
        assert post(server, "/api/finish", {}, headers)[0] == 200
        assert post(server, "/api/advance", {"minutes": 1}, headers)[0] == 400
        assert post(server, "/api/finish", {}, headers)[0] == 400
        assert post(server, "/api/decide", {"action_id": "declare-recovery", "evidence_ids": [],
                    "rationale": "A post-finish edit."}, headers)[0] == 400
        assert request(server, "GET", "/api/export")[0] == 200


def test_only_literal_loopback_can_bind():
    for host in ("0.0.0.0", "localhost", "::", "192.168.1.1"):
        with pytest.raises(RehearsalError, match="loopback"):
            create_server("kafka-lag", host)


@pytest.mark.parametrize("length,status", [("²", 411), ("9" * 5000, 413), ("-1", 411)])
def test_extreme_content_length_is_rejected_without_integer_conversion_error(length, status):
    with running() as server:
        headers = {**authorized(server), "Content-Length": length}
        assert request(server, "POST", "/api/advance", "{}", headers)[0] == status
        assert request(server, "GET", "/api/state")[0] == 200


def test_deep_json_is_rejected_and_server_remains_available():
    with running() as server:
        assert request(server, "POST", "/api/advance", "[" * 1200 + "]" * 1200,
                       authorized(server))[0] == 400
        assert request(server, "GET", "/api/state")[0] == 200


def test_duplicate_length_and_transfer_encoding_are_rejected():
    with running() as server:
        headers = authorized(server)
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.putrequest("POST", "/api/advance")
        for key, value in headers.items():
            connection.putheader(key, value)
        connection.putheader("Content-Length", "2")
        connection.putheader("Content-Length", "2")
        connection.endheaders(b"{}")
        response = connection.getresponse()
        assert response.status == 411
        response.read()
        connection.close()
        assert request(server, "POST", "/api/advance", "{}",
                       {**headers, "Transfer-Encoding": "chunked"})[0] == 400
