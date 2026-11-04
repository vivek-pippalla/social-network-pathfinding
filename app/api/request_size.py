"""ASGI request-body size limit with the standard API error envelope."""

import json
import re
import uuid


class RequestBodyLimitMiddleware:
    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        declared_length = headers.get(b"content-length")
        if declared_length is not None:
            try:
                too_large = int(declared_length) > self.max_bytes
            except ValueError:
                too_large = False
            if too_large:
                await self._respond_too_large(scope, headers, send)
                return

        chunks = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunks.extend(message.get("body", b""))
            if len(chunks) > self.max_bytes:
                await self._respond_too_large(scope, headers, send)
                return
            if not message.get("more_body", False):
                break

        first_message = {
            "type": "http.request",
            "body": bytes(chunks),
            "more_body": False,
        }

        async def replay_receive():
            nonlocal first_message
            if first_message is not None:
                message_to_replay = first_message
                first_message = None
                return message_to_replay
            return await receive()

        await self.app(scope, replay_receive, send)

    async def _respond_too_large(self, scope, headers, send):
        state_request_id = scope.get("state", {}).get("request_id")
        inbound_id = headers.get(b"x-request-id", b"").decode("latin-1")
        request_id = state_request_id or (
            inbound_id
            if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", inbound_id)
            else uuid.uuid4().hex
        )
        body = json.dumps(
            {
                "error": {
                    "code": "REQUEST_TOO_LARGE",
                    "message": "The request body exceeds the configured limit.",
                    "request_id": request_id,
                    "details": [],
                }
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"x-request-id", request_id.encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
