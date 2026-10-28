from fastapi import WebSocket, WebSocketDisconnect

import json


# Super simple audio streaming POC
class AudioSocketHandler:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.chunk_count = 0

    async def handle(self):
        await self.websocket.accept()
        await self.on_connect()

        try:
            while True:
                message = await self.websocket.receive()

                if message.get("bytes") is not None:
                    await self.on_audio_chunk(message["bytes"])
                elif message.get("text") is not None:
                    await self.on_text_message(message["text"])
        except WebSocketDisconnect:
            await self.on_disconnect()

    async def on_connect(self):
        await self.websocket.send_json({"event": "connected"})

    async def on_audio_chunk(self, data: bytes):
        self.chunk_count += 1
        await self.websocket.send_json(
            {"event": "chunk", "seq": self.chunk_count, "bytes": len(data)}
        )

        await self.websocket.send_bytes(data)

    async def on_text_message(self, data: str):
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            payload = {"raw": data}

        if payload.get("event") == "stop":
            await self.websocket.send_json(
                {"event": "stopped", "total_chunks": self.chunk_count}
            )

    async def on_disconnect(self):
        pass
