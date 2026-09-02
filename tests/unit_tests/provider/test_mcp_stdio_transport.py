from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from mcp import ClientSession

from langbot.pkg.provider.tools.loaders.mcp_stdio import authenticated_websocket_client


class _FakeWebSocket:
    def __init__(self) -> None:
        self.incoming: asyncio.Queue[str] = asyncio.Queue()
        self.sent: list[dict] = []
        self.response_frame_count = 0

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        return await self.incoming.get()

    async def send(self, payload: str) -> None:
        message = json.loads(payload)
        self.sent.append(message)
        method = message.get('method')
        if method == 'initialize':
            response = {
                'jsonrpc': '2.0',
                'id': message['id'],
                'result': {
                    'protocolVersion': '2025-06-18',
                    'capabilities': {'tools': {}},
                    'serverInfo': {'name': 'split-frame-test', 'version': '1.0'},
                },
            }
            await self.incoming.put(json.dumps(response) + '\n')
        elif method == 'tools/list':
            description = 'x' * (128 * 1024)
            response = {
                'jsonrpc': '2.0',
                'id': message['id'],
                'result': {
                    'tools': [
                        {
                            'name': 'large-tool',
                            'description': description,
                            'inputSchema': {'type': 'object', 'properties': {}},
                        }
                    ]
                },
            }
            encoded = json.dumps(response) + '\n'
            frames = [encoded[offset : offset + 64 * 1024] for offset in range(0, len(encoded), 64 * 1024)]
            self.response_frame_count = len(frames)
            for frame in frames:
                await self.incoming.put(frame)


@pytest.mark.asyncio
async def test_authenticated_websocket_client_reassembles_split_jsonrpc_response(monkeypatch: pytest.MonkeyPatch):
    import websockets.asyncio.client

    websocket = _FakeWebSocket()
    connection_args: dict = {}

    @asynccontextmanager
    async def fake_connect(url: str, **kwargs):
        connection_args['url'] = url
        connection_args.update(kwargs)
        yield websocket

    monkeypatch.setattr(websockets.asyncio.client, 'connect', fake_connect)

    headers = {'X-LangBot-Box-Control-Token': 'secret'}
    async with authenticated_websocket_client('ws://box.example/process', headers) as (read, write):
        async with ClientSession(read, write) as session:
            init_result = await asyncio.wait_for(session.initialize(), timeout=1)
            tools_result = await asyncio.wait_for(session.list_tools(), timeout=1)

    assert init_result.serverInfo.name == 'split-frame-test'
    assert len(tools_result.tools) == 1
    assert tools_result.tools[0].name == 'large-tool'
    assert len(tools_result.tools[0].description or '') == 128 * 1024
    assert websocket.response_frame_count > 1
    assert connection_args['url'] == 'ws://box.example/process'
    assert connection_args['additional_headers'] == headers
    assert connection_args['proxy'] is None


@pytest.mark.asyncio
async def test_authenticated_websocket_client_splits_coalesced_jsonrpc_messages(monkeypatch: pytest.MonkeyPatch):
    import websockets.asyncio.client

    websocket = _FakeWebSocket()

    @asynccontextmanager
    async def fake_connect(_url: str, **_kwargs):
        yield websocket

    monkeypatch.setattr(websockets.asyncio.client, 'connect', fake_connect)

    first = {'jsonrpc': '2.0', 'id': 1, 'result': {'value': 'first'}}
    second = {'jsonrpc': '2.0', 'id': 2, 'result': {'value': 'second'}}
    await websocket.incoming.put(f'{json.dumps(first)}\n{json.dumps(second)}\n')

    async with authenticated_websocket_client('ws://box.example/process', {}) as (read, write):
        async with read, write:
            first_message = await asyncio.wait_for(read.receive(), timeout=1)
            second_message = await asyncio.wait_for(read.receive(), timeout=1)

    assert first_message.message.root.id == 1
    assert second_message.message.root.id == 2
