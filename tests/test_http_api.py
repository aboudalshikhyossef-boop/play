import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from server.app import create_server


class HTTPAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp.name) / "http.sqlite3")
        self.server = create_server("127.0.0.1", 0, db_path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method, path, data=None, cookie=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Host": "127.0.0.1:%s" % self.port}
        if data is not None:
            headers["Content-Type"] = "application/json; charset=UTF-8"
            headers["Origin"] = "http://127.0.0.1:%s" % self.port
        if cookie:
            headers["Cookie"] = cookie
        body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        if raw:
            decoded = raw.decode("utf-8")
            try:
                payload = json.loads(decoded)
            except ValueError:
                payload = decoded
        else:
            payload = {}
        result = (response.status, payload, response.getheader("Set-Cookie"))
        connection.close()
        return result

    def test_home_and_health_routes(self):
        status, payload, _ = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        status, payload, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("CHAOS FAMILY BATTLE", payload)
        status, payload, _ = self.request("GET", "/static/app.js")
        self.assertEqual(status, 200)
        self.assertIn("XMLHttpRequest", payload)
        status, payload, _ = self.request("GET", "/compatibility/")
        self.assertEqual(status, 200)
        self.assertIn("الرسائل التي استلمها الخادم", payload)

    def test_compatibility_message_is_shared_from_server_feed(self):
        status, payload, _ = self.request("POST", "/api/messages", {"message": "رسالة من الهاتف"})
        self.assertEqual(status, 201)
        self.assertTrue(payload["stored_by_server"])
        status, feed, _ = self.request("GET", "/api/messages?after_id=0")
        self.assertEqual(status, 200)
        self.assertEqual(feed["messages"][0]["message"], "رسالة من الهاتف")

    def test_room_cookie_auth_join_capacity_and_ready(self):
        status, created, cookie = self.request("POST", "/api/rooms", {"name": "يوسف"})
        self.assertEqual(status, 201)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertNotIn("session_token", json.dumps(created))
        creator_cookie = cookie.split(";", 1)[0]

        status, me, _ = self.request("GET", "/api/me", cookie=creator_cookie)
        self.assertEqual(status, 200)
        self.assertEqual(me["room"]["you"]["seat"], 1)

        cookies = [creator_cookie]
        for name in ("Android One", "Android Two", "iPhone"):
            status, joined, set_cookie = self.request(
                "POST", "/api/rooms/%s/join" % created["invite_code"], {"name": name}
            )
            self.assertEqual(status, 201)
            cookies.append(set_cookie.split(";", 1)[0])

        status, _full, _ = self.request(
            "POST", "/api/rooms/%s/join" % created["invite_code"], {"name": "Fifth"}
        )
        self.assertEqual(status, 409)

        for cookie_value in cookies:
            status, ready, _ = self.request(
                "POST", "/api/rooms/%s/ready" % created["invite_code"], {"ready": True}, cookie_value
            )
            self.assertEqual(status, 200)
        status, room, _ = self.request(
            "GET", "/api/rooms/%s" % created["invite_code"], cookie=cookies[0]
        )
        self.assertEqual(status, 200)
        self.assertTrue(room["room"]["all_ready"])
        self.assertEqual(room["room"]["occupied"], 4)

    def test_room_endpoint_requires_session(self):
        status, payload, _ = self.request("GET", "/api/rooms/ABCDEFGHJK")
        self.assertEqual(status, 401)
        self.assertFalse(payload["ok"])

    def test_cross_origin_mutation_is_rejected(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        body = json.dumps({"name": "Intruder"}).encode("utf-8")
        connection.request(
            "POST", "/api/rooms", body=body,
            headers={
                "Host": "127.0.0.1:%s" % self.port,
                "Content-Type": "application/json",
                "Origin": "https://attacker.invalid",
            },
        )
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(response.status, 403)
        self.assertEqual(payload["code"], "origin_rejected")
        connection.close()

    def test_room_creation_rate_limit_is_enforced(self):
        statuses = []
        for index in range(6):
            status, _payload, _cookie = self.request("POST", "/api/rooms", {"name": "Creator %s" % index})
            statuses.append(status)
        self.assertEqual(statuses[:5], [201, 201, 201, 201, 201])
        self.assertEqual(statuses[5], 429)


    def test_three_player_match_starts_and_freezes_room_membership(self):
        status, created, cookie = self.request("POST", "/api/rooms", {"name": "Host"})
        self.assertEqual(status, 201)
        creator_cookie = cookie.split(";", 1)[0]
        cookies = [creator_cookie]

        for name in ("Android One", "Android Two"):
            status, joined, set_cookie = self.request(
                "POST", "/api/rooms/%s/join" % created["invite_code"], {"name": name}
            )
            self.assertEqual(status, 201)
            cookies.append(set_cookie.split(";", 1)[0])

        for cookie_value in cookies:
            status, ready, _ = self.request(
                "POST", "/api/rooms/%s/ready" % created["invite_code"],
                {"ready": True}, cookie_value
            )
            self.assertEqual(status, 200)
            self.assertTrue(ready["room"]["all_ready"])

        status, match, _ = self.request(
            "POST", "/api/rooms/%s/start" % created["invite_code"], {}, creator_cookie
        )
        self.assertEqual(status, 201)
        self.assertEqual(match["phase"], "actions")
        self.assertEqual(match["player_count"], 3)

        status, snapshot, _ = self.request(
            "GET", "/api/rooms/%s/match" % created["invite_code"], cookie=creator_cookie
        )
        self.assertEqual(status, 200)
        self.assertEqual(snapshot["match_id"], match["match_id"])

        status, _late, _ = self.request(
            "POST", "/api/rooms/%s/join" % created["invite_code"],
            {"name": "Late Player"}
        )
        self.assertEqual(status, 409)

        status, action_state, _ = self.request(
            "POST", "/api/rooms/%s/match/action" % created["invite_code"],
            {"request_id": "api-action-0001", "action": "pass", "amount": 0},
            creator_cookie
        )
        self.assertEqual(status, 200)
        self.assertEqual(action_state["phase"], "actions")
        self.assertTrue(action_state["private"]["action_submitted"])


if __name__ == "__main__":
    unittest.main()
