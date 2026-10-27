"""Minimal WebSocket server (RFC 6455) on asyncio, standard library only.

Enough for the stream: text messages, ping/pong, close, fragmented client messages.
No extensions (no permessage-deflate) and no subprotocols. Plain HTTP GET /healthz
answers 200 for the Container Apps health probes.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import struct

log = logging.getLogger(__name__)

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_HEADER_BYTES = 8192
MAX_MESSAGE_BYTES = 64 * 1024  # the UI only sends subscribe

OP_CONT, OP_TEXT, OP_BINARY, OP_CLOSE, OP_PING, OP_PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA


class ConnectionClosed(Exception):
    pass


def accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + GUID).encode("ascii")).digest()).decode("ascii")


def encode_frame(opcode: int, payload: bytes, mask: bytes | None = None) -> bytes:
    """One final frame. Servers send unmasked frames; ``mask`` is for test clients."""
    head = bytes([0x80 | opcode])
    length = len(payload)
    mask_bit = 0x80 if mask else 0
    if length < 126:
        head += bytes([mask_bit | length])
    elif length < 1 << 16:
        head += bytes([mask_bit | 126]) + struct.pack("!H", length)
    else:
        head += bytes([mask_bit | 127]) + struct.pack("!Q", length)
    if mask:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        head += mask
    return head + payload


async def read_frame(reader: asyncio.StreamReader, *, require_mask: bool) -> tuple[bool, int, bytes]:
    """``(fin, opcode, payload)``. Raises ConnectionClosed on EOF or a protocol error."""
    try:
        b1, b2 = await reader.readexactly(2)
        length = b2 & 0x7F
        if length == 126:
            (length,) = struct.unpack("!H", await reader.readexactly(2))
        elif length == 127:
            (length,) = struct.unpack("!Q", await reader.readexactly(8))
        masked = bool(b2 & 0x80)
        if require_mask and not masked:
            raise ConnectionClosed("client frame without mask")
        if length > MAX_MESSAGE_BYTES:
            raise ConnectionClosed("frame too large")
        mask = await reader.readexactly(4) if masked else b""
        payload = await reader.readexactly(length)
    except (asyncio.IncompleteReadError, ConnectionError) as exc:
        raise ConnectionClosed(str(exc)) from exc
    if masked:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return bool(b1 & 0x80), b1 & 0x0F, payload


class WebSocket:
    """Server side of one connection."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, path: str):
        self.reader = reader
        self.writer = writer
        self.path = path
        self.closed = False
        self._lock = asyncio.Lock()

    async def _send_frame(self, opcode: int, payload: bytes) -> None:
        if self.closed:
            raise ConnectionClosed("already closed")
        async with self._lock:
            try:
                self.writer.write(encode_frame(opcode, payload))
                await self.writer.drain()
            except (ConnectionError, RuntimeError) as exc:
                self.closed = True
                raise ConnectionClosed(str(exc)) from exc

    async def send(self, text: str) -> None:
        await self._send_frame(OP_TEXT, text.encode("utf-8"))

    async def recv(self) -> str:
        """Next text message. Answers pings on its own. Raises ConnectionClosed when the client leaves."""
        parts: list[bytes] = []
        while True:
            fin, opcode, payload = await read_frame(self.reader, require_mask=True)
            if opcode == OP_PING:
                await self._send_frame(OP_PONG, payload)
                continue
            if opcode == OP_PONG:
                continue
            if opcode == OP_CLOSE:
                await self.close(payload[:2] if len(payload) >= 2 else struct.pack("!H", 1000))
                raise ConnectionClosed("client closed")
            if opcode in (OP_TEXT, OP_BINARY, OP_CONT):
                parts.append(payload)
                if sum(map(len, parts)) > MAX_MESSAGE_BYTES:
                    await self.close(struct.pack("!H", 1009))
                    raise ConnectionClosed("message too large")
                if fin:
                    try:
                        return b"".join(parts).decode("utf-8")
                    except UnicodeDecodeError as exc:
                        await self.close(struct.pack("!H", 1007))
                        raise ConnectionClosed("invalid utf-8") from exc
                continue
            await self.close(struct.pack("!H", 1002))
            raise ConnectionClosed(f"unknown opcode {opcode}")

    async def close(self, code_and_reason: bytes = struct.pack("!H", 1000)) -> None:
        if self.closed:
            return
        try:
            await self._send_frame(OP_CLOSE, code_and_reason)
        except ConnectionClosed:
            pass
        self.closed = True
        try:
            self.writer.close()
        except RuntimeError:
            pass


async def _http_reply(writer: asyncio.StreamWriter, status: str, body: str = "") -> None:
    data = body.encode("utf-8")
    writer.write(f"HTTP/1.1 {status}\r\nContent-Type: text/plain; charset=utf-8\r\n"
                 f"Content-Length: {len(data)}\r\nConnection: close\r\n\r\n".encode("ascii") + data)
    try:
        await writer.drain()
    finally:
        writer.close()


async def _file_reply(writer: asyncio.StreamWriter, content_type: str, gzipped: bytes) -> None:
    """A static file, already gzipped, that any web page may fetch (CORS)."""
    writer.write((f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\nContent-Encoding: gzip\r\n"
                  f"Content-Length: {len(gzipped)}\r\nAccess-Control-Allow-Origin: *\r\n"
                  "Cache-Control: public, max-age=300\r\nConnection: close\r\n\r\n").encode("ascii") + gzipped)
    try:
        await writer.drain()
    finally:
        writer.close()


async def handshake(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                    files: dict[str, tuple[str, bytes]] | None = None) -> WebSocket | None:
    """Upgrade the connection, or answer plain HTTP (health check, static ``files``, 404, 400) and return None.

    ``files`` maps a path such as ``/positions/m001`` to its content type and gzipped body."""
    try:
        raw = await reader.readuntil(b"\r\n\r\n")
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError):
        writer.close()
        return None
    if len(raw) > MAX_HEADER_BYTES:
        await _http_reply(writer, "431 Request Header Fields Too Large")
        return None
    lines = raw.decode("latin-1").split("\r\n")
    try:
        method, target, _ = lines[0].split(" ", 2)
    except ValueError:
        await _http_reply(writer, "400 Bad Request")
        return None
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
    path = target.split("?", 1)[0]

    is_upgrade = "websocket" in headers.get("upgrade", "").lower() and "upgrade" in headers.get("connection", "").lower()
    if not is_upgrade:
        if method == "GET" and path in ("/healthz", "/"):
            await _http_reply(writer, "200 OK", "ok\n")
        elif method == "GET" and files and path in files:
            await _file_reply(writer, *files[path])
        else:
            await _http_reply(writer, "404 Not Found")
        return None
    key = headers.get("sec-websocket-key")
    if method != "GET" or not key or headers.get("sec-websocket-version") != "13":
        await _http_reply(writer, "400 Bad Request", "WebSocket version 13 with Sec-WebSocket-Key required\n")
        return None
    writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                  f"Sec-WebSocket-Accept: {accept_key(key)}\r\n\r\n").encode("ascii"))
    await writer.drain()
    return WebSocket(reader, writer, path)
