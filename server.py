#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoiceStudio Mini · local server
===============================
复刻 VoiceStudio 的「本地优先」后端：仅在本机回环 127.0.0.1:3900 监听，
免 server key，提供 REST / SSE / WebSocket(描述) / MCP(JSON-RPC) 四种接入，
与本机前端或任意 Agent 通信，数据默认不离开本机。

启动：  python3 server.py            # 默认 127.0.0.1:3900
绑定说明：刻意只绑回环地址，等价于上游「外发需显式 opt-in」的数据路径。
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import core

HOST, PORT = "127.0.0.1", 3900


def _cors(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


def _read_body(handler):
    try:
        length = int(handler.headers.get("Content-Length", 0))
        raw = handler.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        return {}


def _json(handler, code, obj):
    payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    _cors(handler)
    handler.end_headers()
    handler.wfile.write(payload)


MCP_TOOLS = [
    {"name": "vs_clone", "description": "从参考音频克隆音色档案",
     "inputSchema": {"type": "object", "properties": {"reference": {"type": "string"}}}},
    {"name": "vs_design", "description": "用显式参数设计音色",
     "inputSchema": {"type": "object", "properties": {"params": {"type": "object"}}}},
    {"name": "vs_convert", "description": "按目标音色转换/合成语音",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}}},
    {"name": "vs_dub", "description": "视频配音流水线",
     "inputSchema": {"type": "object", "properties": {"source": {"type": "string"}, "lang": {"type": "string"}}}},
    {"name": "vs_registry", "description": "引擎与语言注册表",
     "inputSchema": {"type": "object"}},
]


class Handler(BaseHTTPRequestHandler):
    server_version = "VoiceStudioMini/0.1 (local-first)"

    # 不打印每请求日志，保持安静
    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        _cors(self)
        self.end_headers()

    def _dispatch(self):
        parsed = urlparse(self.path)
        path = parsed.path
        q = parse_qs(parsed.query)

        if path == "/" or path == "/api/health":
            return 200, {
                "service": "VoiceStudio Mini",
                "bind": HOST, "port": PORT,
                "local_first": True, "requires_server_key": False,
                "protocols": ["rest", "sse", "websocket", "mcp"],
                "engine": {"tts": core.TTS_ENGINES.__len__(),
                           "asr": core.ASR_ENGINES.__len__(),
                           "languages": core.LANGUAGE_COUNT},
                "status": "ok",
            }

        if path == "/api/registry":
            return 200, core.REGISTRY

        if path == "/api/clone" and self.command == "POST":
            b = _read_body(self)
            return 200, core.clone_from_audio(b.get("reference", "reference.wav"),
                                              b.get("tts_engine", "xtts_v2"))

        if path == "/api/design" and self.command == "POST":
            b = _read_body(self)
            return 200, core.design_by_params(b.get("params", {}))

        if path == "/api/convert" and self.command == "POST":
            b = _read_body(self)
            target = {"seed": b.get("target_seed", core._hash_str("clone:reference.wav")),
                      "tts_engine": b.get("tts_engine", "xtts_v2")}
            return 200, core.convert_voice(b.get("text", "你好世界"), target,
                                           b.get("asr_engine", "whisper"))

        if path == "/api/dub" and self.command == "GET":
            src = q.get("source", ["sample.mp4"])[0]
            lang = q.get("lang", ["en-US"])[0]
            return 200, core.video_dub(src, lang)

        if path == "/api/stream" and self.command == "GET":
            return self._sse()

        if path == "/api/mcp" and self.command == "POST":
            return self._mcp(_read_body(self))

        return 404, {"error": "not_found", "path": path}

    def _sse(self):
        """SSE：模拟配音流水线进度事件流。"""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        _cors(self)
        self.end_headers()
        steps = ["transcribe", "translate", "keep_original_bed", "synthesize", "mux"]
        try:
            for i, s in enumerate(steps, 1):
                evt = json.dumps({"progress": i / len(steps), "step": s, "status": "done"})
                self.wfile.write(f"data: {evt}\n\n".encode("utf-8"))
                self.wfile.flush()
                time.sleep(0.4)
            self.wfile.write(f"data: {json.dumps({'done': True})}\n\n".encode("utf-8"))
            self.wfile.flush()
        except Exception:
            pass

    def _mcp(self, body):
        method = body.get("method")
        if method == "tools/list":
            return 200, {"jsonrpc": "2.0", "id": body.get("id"), "result": {"tools": MCP_TOOLS}}
        if method == "tools/call":
            name = body.get("params", {}).get("name")
            args = body.get("params", {}).get("arguments", {})
            if name == "vs_clone":
                res = core.clone_from_audio(args.get("reference", "reference.wav"))
            elif name == "vs_design":
                res = core.design_by_params(args.get("params", {}))
            elif name == "vs_convert":
                res = core.convert_voice(args.get("text", "你好"), {"seed": "x"})
            elif name == "vs_dub":
                res = core.video_dub(args.get("source", "x"), args.get("lang", "en-US"))
            elif name == "vs_registry":
                res = core.REGISTRY
            else:
                return 200, {"jsonrpc": "2.0", "id": body.get("id"),
                             "error": {"code": -32601, "message": f"unknown tool {name}"}}
            return 200, {"jsonrpc": "2.0", "id": body.get("id"), "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]}}
        return 200, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32601, "message": "method not found"}}

    def do_GET(self):
        code, obj = self._dispatch()
        if code == 200 and isinstance(obj, dict) and "status" in obj and self.path == "/":
            _json(self, code, obj)
        else:
            _json(self, code, obj)

    def do_POST(self):
        code, obj = self._dispatch()
        _json(self, code, obj)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    httpd = ThreadingHTTPServer((HOST, port), Handler)
    print(f"VoiceStudio Mini 本地 API 已启动 → http://{HOST}:{port}")
    print(f"  local_first=True  requires_server_key=False  (仅本机回环可访问)")
    print(f"  试试：curl http://{HOST}:{port}/api/registry")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
