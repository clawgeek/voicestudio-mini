# VoiceStudio Mini · 技能说明（SKILLS）

> 受 [debpalash/VoiceStudio](https://github.com/debpalash/VoiceStudio) 启发的最小可跑通内核。
> 本仓库是**结构演示**：用确定性算法复刻其「本地优先数据路径 + 三入口 + 引擎矩阵 + 视频配音流水线 + AudioSeal 水印 + 本地回环 API」，不含真实声学模型。**正式生产请使用上游仓库**（本体 AGPL-3.0，默认权重 CC-BY-NC）。

## 它解决什么
云端语音按次收费、账号锁定、数据外发。VoiceStudio 把路径反过来：**默认本地，外发显式 opt-in**——数据不离开本机，agent 只拿到结果。

## 三大入口
| 入口 | 方法 | 产物 |
|------|------|------|
| ① 克隆 FROM AUDIO | `clone_from_audio(reference)` | 可复现的音色档案（seed + pitch/formant/speed/timbre）|
| ② 创声 BY DESIGN | `design_by_params({pitch,formant,speed,timbre})` | 由显式参数合成的音色档案（含合法区间校验）|
| ③ 转换 CONVERT | `convert_voice(text, target_profile)` | 语音转语音 / 合成，标注 source/target + 水印 |

## 引擎矩阵（结构演示，数目与上游一致）
- **16** 个 TTS 引擎 · **11** 个 ASR 引擎 · **646** 语言/方言注册表
- 真实引擎清单与质量以官方仓库为准；646 为声明覆盖数。

## 视频配音流水线
`源(文件/URL) → transcribe → translate → keep_original_bed → synthesize → mux`
保留原始人声底床，避免机械感；合成音轨默认嵌入 AudioSeal 水印。

## 本地回环 API（127.0.0.1:3900，免 server key）
同源暴露四种协议，供桌面端或任意 Agent 调用：
- **REST**：`GET /api/health`、`GET /api/registry`、`POST /api/clone`、`POST /api/design`、`POST /api/convert`、`GET /api/dub`
- **SSE**：`GET /api/stream`（配音进度流）
- **WebSocket**：实时双向（README 有协议说明）
- **MCP**：`POST /api/mcp`（JSON-RPC `tools/list` / `tools/call`，暴露 `vs_clone/vs_design/vs_convert/vs_dub/vs_registry`）

刻意只绑回环地址 == 「外发需显式 opt-in」的数据路径。

## 质量门（脚本化拦截）
9 道门覆盖：克隆可复现、创声参数合法、转换带水印、配音 5 步完成、引擎/语言在册、默认水印、本地优先、API 仅绑回环且免 key。任一 FAIL 即判定未达交付标准。

## 如何运行
```bash
pip install -U .            # 仅占位；本 Demo 零依赖
python3 pipeline.py         # headless：落 output/*.json + 跑质量门
python3 server.py           # 启动本地 API（127.0.0.1:3900）
# 浏览器打开 index.html（自动对接本地 API，断网降级为内置模拟）
```
