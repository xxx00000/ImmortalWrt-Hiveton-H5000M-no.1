"""Run against the fetched and patched package; no router or external webhook needed."""
import asyncio
import importlib.util
import json
import pathlib
import sys
import unittest

import websockets

SOURCE = pathlib.Path(sys.argv.pop(1))


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        spec = importlib.util.spec_from_file_location("at_server", SOURCE)
        self.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.module
        spec.loader.exec_module(self.module)

    async def deliver(self, status, response):
        received = []

        async def handler(reader, writer):
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next(int(line.split(b":", 1)[1]) for line in headers.split(b"\r\n")
                          if line.lower().startswith(b"content-length:"))
            received.append(json.loads(await reader.readexactly(length)))
            body = response.encode()
            writer.write(f"HTTP/1.1 {status} Test\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode() + body)
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        channel = self.module.WeChatNotification(f"http://127.0.0.1:{port}/webhook")
        channel.retry_delay = 0
        async with server:
            # The HTTP server shares the event loop: blocking HTTP here would deadlock.
            with self.assertLogs(self.module.logger, level="INFO") as logs:
                await asyncio.wait_for(channel._do_send("test", "短信测试"), 10)
        self.assertTrue(all(item == {"msgtype": "text", "text": {"content": "短信测试"}} for item in received))
        return received, "\n".join(logs.output)

    async def test_webhook_posts_json_without_aiohttp(self):
        requests, logs = await self.deliver(200, '{"errcode":0}')
        self.assertEqual(len(requests), 1)
        self.assertIn("发送成功", logs)

    async def test_api_failure_is_retried_and_not_reported_as_success(self):
        requests, logs = await self.deliver(200, '{"errcode":40013}')
        self.assertEqual(len(requests), 3)
        self.assertNotIn("发送成功", logs)

    async def test_http_error_is_retried(self):
        requests, logs = await self.deliver(503, '{}')
        self.assertEqual(len(requests), 3)
        self.assertNotIn("发送成功", logs)

    async def test_invalid_json_is_retried(self):
        requests, logs = await self.deliver(200, 'invalid')
        self.assertEqual(len(requests), 3)
        self.assertNotIn("发送成功", logs)

    async def test_websocket_auth_and_ping_with_feed_version(self):
        self.module.WEBSOCKET_CONFIG = {"AUTH_KEY": "test-only-key"}
        service = self.module.WebSocketServer(self.module.ATClient())
        async with websockets.serve(service.handle_client, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
                await client.send('{"auth_key":"test-only-key"}')
                self.assertTrue(json.loads(await client.recv())["success"])
                await client.send("ping")
                self.assertEqual(await client.recv(), "pong")

    async def test_websocket_rejects_wrong_key(self):
        self.module.WEBSOCKET_CONFIG = {"AUTH_KEY": "test-only-key"}
        service = self.module.WebSocketServer(self.module.ATClient())
        async with websockets.serve(service.handle_client, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
                await client.send('{"auth_key":"wrong"}')
                self.assertEqual(json.loads(await client.recv())["error"], "Authentication failed")
                with self.assertRaises(websockets.exceptions.ConnectionClosed):
                    await client.recv()


if __name__ == "__main__":
    unittest.main()
