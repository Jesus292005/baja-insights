"""Stream service (contract v1.1): replay logic and a real WebSocket round trip."""

import helpers  # noqa: F401  (puts src/ on sys.path)
import asyncio
import base64
import json
import os
import struct
import unittest

from baja_insights.stream import Match, MatchClock, StreamServer, load_files, load_matches
from baja_insights.stream import messages as msg
from baja_insights.stream.ws import OP_CLOSE, OP_PING, OP_PONG, OP_TEXT, accept_key, encode_frame, read_frame
from helpers import DATA, validator

M001 = DATA / "m001"


def m001() -> Match:
    return Match.from_files(M001 / "events.jsonl", M001 / "overlays.json")


class FakeTime:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class ReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.match = m001()

    def test_scoreline_comes_from_the_events(self):
        m = self.match
        self.assertEqual((m.home, m.away), ("Bahía FC", "Real Cardón"))
        self.assertEqual(m.scoreline_at(0), {"home": 0, "away": 0})
        self.assertEqual(m.scoreline_at(1059), {"home": 0, "away": 0})
        self.assertEqual(m.scoreline_at(1060), {"home": 0, "away": 1})
        self.assertEqual(m.scoreline_at(3789), {"home": 1, "away": 1})
        self.assertEqual(m.state_times(0, 5400), [1060, 2700, 3789, 5400])

    def test_orders_between_is_half_open(self):
        first = self.match.orders[0]["show_at_s"]
        self.assertEqual(self.match.orders_between(first - 1, first)[0], self.match.orders[0])
        self.assertNotIn(self.match.orders[0], self.match.orders_between(first, first + 1))

    def test_resend_includes_graphics_still_on_screen(self):
        goal = next(o for o in self.match.orders if o["type"] == "goal_analysis")
        dropped_at = goal["show_at_s"] + 3  # connection lost while the goal graphic was showing
        resent = self.match.orders_to_resend(dropped_at, dropped_at + 30)
        self.assertIn(goal, resent)
        for order in resent:
            self.assertGreater(order["show_at_s"] + order["duration_s"], dropped_at)
            self.assertLessEqual(order["show_at_s"], dropped_at + 30)
        # the old rule (show_at_s >= from_t_s) would have lost it
        self.assertLess(goal["show_at_s"], dropped_at)

    def test_first_subscribe_gets_only_what_is_on_screen(self):
        goal = next(o for o in self.match.orders if o["type"] == "goal_analysis")
        now = goal["show_at_s"] + 1
        on_screen = self.match.orders_to_resend(None, now)
        self.assertIn(goal, on_screen)
        self.assertTrue(all(o["show_at_s"] <= now < o["show_at_s"] + o["duration_s"] for o in on_screen))

    def test_clock_is_shared_and_capped(self):
        fake = FakeTime()
        clock = MatchClock(speed=60, start_at=0, now=fake)
        self.assertEqual(clock.t_s(), 0)
        clock.start()
        fake.now += 10
        self.assertEqual(clock.t_s(), 600)
        clock.start()  # a second viewer does not restart it
        self.assertEqual(clock.t_s(), 600)
        self.assertAlmostEqual(clock.wall_at(1200), 120.0)
        fake.now += 1000
        self.assertEqual(clock.t_s(), 5520)
        self.assertTrue(clock.finished())

    def test_clock_message(self):
        self.assertEqual(msg.clock("m001", 2699, 1.0),
                         {"kind": "clock", "match_id": "m001", "t_s": 2699, "period": 1, "phase": "live", "speed": 1.0})
        self.assertEqual((msg.clock("m001", 2700, 1.0)["phase"], msg.clock("m001", 2700, 1.0)["period"]), ("half_time", 1))
        self.assertEqual((msg.clock("m001", 2701, 1.0)["phase"], msg.clock("m001", 2701, 1.0)["period"]), ("live", 2))
        self.assertEqual(msg.clock("m001", 5400, 1.0)["phase"], "full_time")

    def test_half_time_pause(self):
        fake = FakeTime()
        clock = MatchClock(speed=60, start_at=2640, half_time_pause_s=5, now=fake)
        clock.start()
        fake.now += 1  # 60 match seconds later: 45:00
        self.assertEqual((clock.t_s(), clock.at_half_time()), (2700, True))
        fake.now += 4.9
        self.assertEqual((clock.t_s(), clock.at_half_time()), (2700, True))
        fake.now += 1.1  # 1 s after the pause
        self.assertEqual((clock.t_s(), clock.at_half_time()), (2760, False))
        self.assertAlmostEqual(clock.wall_at(2760), 107.0)
        self.assertAlmostEqual(clock.wall_at(2700), 101.0)

    def test_every_message_shape_matches_the_contract(self):
        stream = validator("stream")
        if stream is None:
            self.skipTest("jsonschema not installed")
        m = self.match
        samples = [m.state_at(0), m.state_at(5400), msg.overlay(m.orders[0]), msg.clock("m001", 0, 60.0),
                   msg.clock("m001", 2700, 60.0, True), msg.clock("m001", 5520, 1.0),
                   msg.error(msg.MATCH_NOT_FOUND, "x"), msg.error(msg.STREAM_ENDED, "x"),
                   msg.error(msg.SERVER_ERROR, "x"), msg.parse_subscribe("nope")[1]]
        for sample in samples:
            self.assertEqual(list(stream.iter_errors(sample)), [], sample)
        subscribe = {"kind": "subscribe", "match_id": "m001", "from_t_s": 0}
        self.assertEqual(list(stream.iter_errors(subscribe)), [])
        self.assertEqual(msg.parse_subscribe(json.dumps(subscribe))[0], {"match_id": "m001", "from_t_s": 0})

    def test_subscribe_parsing(self):
        ok, problem = msg.parse_subscribe('{"kind":"subscribe","match_id":"m001","from_t_s":120}')
        self.assertEqual((ok, problem), ({"match_id": "m001", "from_t_s": 120}, None))
        self.assertEqual(msg.parse_subscribe('{"kind":"subscribe","match_id":"m001"}')[0]["from_t_s"], None)
        for bad in ("nope", "[]", '{"kind":"hello"}', '{"kind":"subscribe"}', '{"type":"subscribe","match_id":"m001"}',
                    '{"kind":"subscribe","match_id":"m001","from_t_s":-1}',
                    '{"kind":"subscribe","match_id":"m001","from_t_s":true}'):
            self.assertIsNone(msg.parse_subscribe(bad)[0], bad)
            self.assertEqual(msg.parse_subscribe(bad)[1]["code"], msg.SERVER_ERROR)

    def test_loads_every_match_in_data(self):
        matches = load_matches(DATA)
        self.assertIn("m001", matches)
        self.assertTrue(matches["m001"].orders)
        self.assertTrue(all(m.score_changes[0] == (0, {"home": 0, "away": 0}) for m in matches.values()))


# ------------------------------------------------------------------ WebSocket round trip
STREAM, OVERLAY = validator("stream"), validator("overlay")


def self_check(message: dict) -> None:
    """Every message the server sends must validate, and the order inside an overlay too."""
    if STREAM is None:
        return
    errors = [e.message for e in STREAM.iter_errors(message)]
    if message.get("kind") == "overlay":
        errors += [e.message for e in OVERLAY.iter_errors(message["order"])]
    assert not errors, (message, errors)
class Client:
    """Tiny WebSocket client for the tests (masked frames, as RFC 6455 requires)."""

    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer

    @classmethod
    async def connect(cls, port: int, path: str = "/ws") -> "Client":
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        key = base64.b64encode(os.urandom(16)).decode()
        writer.write((f"GET {path} HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = (await reader.readuntil(b"\r\n\r\n")).decode()
        assert head.startswith("HTTP/1.1 101"), head
        assert f"Sec-WebSocket-Accept: {accept_key(key)}" in head
        return cls(reader, writer)

    async def send_raw(self, opcode: int, payload: bytes) -> None:
        self.writer.write(encode_frame(opcode, payload, mask=os.urandom(4)))
        await self.writer.drain()

    async def send(self, message) -> None:
        text = message if isinstance(message, str) else json.dumps(message)
        await self.send_raw(OP_TEXT, text.encode())

    async def recv_frame(self, timeout: float = 2.0):
        return await asyncio.wait_for(read_frame(self.reader, require_mask=False), timeout)

    async def recv(self, timeout: float = 2.0) -> dict:
        while True:
            _, opcode, payload = await self.recv_frame(timeout)
            if opcode == OP_TEXT:
                message = json.loads(payload)
                self_check(message)
                return message

    async def collect(self, seconds: float) -> list[dict]:
        out, loop = [], asyncio.get_running_loop()
        end = loop.time() + seconds
        while (left := end - loop.time()) > 0:
            try:
                out.append(await self.recv(left))
            except asyncio.TimeoutError:
                break
        return out

    async def close(self) -> None:
        try:
            await self.send_raw(OP_CLOSE, struct.pack("!H", 1000))
        finally:
            self.writer.close()


class StreamServerTest(unittest.IsolatedAsyncioTestCase):
    SPEED = 600  # 10 match minutes per real second
    START = 1050  # 10 s before the first goal

    async def asyncSetUp(self):
        self.match = m001()
        self.server = StreamServer({"m001": self.match}, speed=self.SPEED, start_at=self.START,
                                   files=load_files(DATA))
        self.tcp = await asyncio.start_server(self.server.handle, "127.0.0.1", 0)
        self.port = self.tcp.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.tcp.close()
        await self.tcp.wait_closed()

    async def test_subscribe_gets_state_clock_goal_and_orders_in_time(self):
        client = await Client.connect(self.port)
        await client.send({"kind": "subscribe", "match_id": "m001", "from_t_s": 0})
        got = await client.collect(1.3)
        await client.close()

        self.assertEqual(got[0]["kind"], "state")
        self.assertEqual(got[0]["scoreline"], {"home": 0, "away": 0})
        self.assertEqual((got[0]["home"], got[0]["away"]), ("Bahía FC", "Real Cardón"))
        clocks = [m for m in got if m["kind"] == "clock"]
        self.assertGreaterEqual(len(clocks), 2, "a clock on subscribe and one per real second")
        self.assertEqual([c["t_s"] for c in clocks], sorted(c["t_s"] for c in clocks))

        goal_state = [m for m in got if m["kind"] == "state" and m["scoreline"] == {"home": 0, "away": 1}]
        self.assertEqual(len(goal_state), 1)
        self.assertEqual(goal_state[0]["t_s"], 1060)

        # every order due while we listened arrived once, in order, and not before its time
        last_t = clocks[-1]["t_s"]
        orders = [m["order"] for m in got if m["kind"] == "overlay"]
        first_clock_t = clocks[0]["t_s"]
        expected = self.match.orders_to_resend(0, first_clock_t) + \
            [o for o in self.match.orders_between(first_clock_t, last_t)]
        self.assertEqual([o["overlay_id"] for o in orders[: len(expected)]], [o["overlay_id"] for o in expected])
        self.assertTrue(orders, "m001 has graphics in the window")
        self.assertEqual([o["show_at_s"] for o in orders], sorted(o["show_at_s"] for o in orders))

    async def test_reconnect_resends_what_was_missed_and_still_on_screen(self):
        first = await Client.connect(self.port)
        await first.send({"kind": "subscribe", "match_id": "m001", "from_t_s": 0})
        seen = await first.collect(0.3)
        await first.close()
        last_t = max(m["t_s"] for m in seen if m["kind"] == "clock")
        await asyncio.sleep(0.4)

        second = await Client.connect(self.port)
        await second.send({"kind": "subscribe", "match_id": "m001", "from_t_s": last_t})
        got = await second.collect(0.2)
        await second.close()

        state = got[0]
        self.assertEqual(state["kind"], "state")
        self.assertGreater(state["t_s"], last_t, "the clock kept running while we were away")
        resent = [m["order"]["overlay_id"] for m in got[1:] if m["kind"] == "overlay"]
        expected = [o["overlay_id"] for o in self.match.orders_to_resend(last_t, state["t_s"])]
        self.assertEqual(resent[: len(expected)], expected)

    async def test_stream_ended_after_the_last_graphic(self):
        server = StreamServer({"m001": self.match}, speed=self.SPEED, start_at=5500)
        tcp = await asyncio.start_server(server.handle, "127.0.0.1", 0)
        try:
            client = await Client.connect(tcp.sockets[0].getsockname()[1])
            await client.send({"kind": "subscribe", "match_id": "m001", "from_t_s": 5500})
            got = await client.collect(1.2)
            await client.close()
        finally:
            tcp.close()
            await tcp.wait_closed()
        ended = [m for m in got if m["kind"] == "error"]
        self.assertEqual([m["code"] for m in ended], ["stream_ended"])
        clocks = [m for m in got if m["kind"] == "clock"]
        self.assertEqual(clocks[-1]["t_s"], 5520)
        self.assertEqual(clocks[-1]["phase"], "full_time")
        last_clock = max(i for i, m in enumerate(got) if m["kind"] == "clock")
        self.assertGreater(last_clock, got.index(ended[0]), "the heartbeat keeps going")

    async def test_errors_and_ping(self):
        client = await Client.connect(self.port)
        await client.send("not json")
        self.assertEqual((await client.recv())["code"], msg.SERVER_ERROR)
        await client.send({"kind": "subscribe", "match_id": "m999", "from_t_s": 0})
        problem = await client.recv()
        self.assertEqual((problem["kind"], problem["code"]), ("error", msg.MATCH_NOT_FOUND))
        await client.send_raw(OP_PING, b"hi")
        _, opcode, payload = await client.recv_frame()
        self.assertEqual((opcode, payload), (OP_PONG, b"hi"))
        await client.close()

    async def test_health_check(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(b"GET /healthz HTTP/1.1\r\nHost: localhost\r\n\r\n")
        reply = await asyncio.wait_for(reader.read(), 2)
        writer.close()
        self.assertTrue(reply.startswith(b"HTTP/1.1 200"))

    async def test_positions_file(self):
        import gzip
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(b"GET /positions/m001 HTTP/1.1\r\nHost: localhost\r\n\r\n")
        reply = await asyncio.wait_for(reader.read(), 5)
        writer.close()
        head, body = reply.split(b"\r\n\r\n", 1)
        self.assertTrue(head.startswith(b"HTTP/1.1 200"))
        self.assertIn(b"Access-Control-Allow-Origin: *", head)
        self.assertIn(b"Content-Encoding: gzip", head)
        positions = json.loads(gzip.decompress(body))
        self.assertEqual((positions["match_id"], positions["illustrative"]), ("m001", True))


if __name__ == "__main__":
    unittest.main()
