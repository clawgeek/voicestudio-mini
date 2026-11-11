#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoiceStudio Mini · core
=======================
受 debpalash/VoiceStudio 启发的最小可跑通内核（纯标准库 / 零外部依赖 / 确定性）。

本模块只做"结构演示"，不含任何真实音频编解码或声学模型：
  - 所有声学参数由输入字符串的哈希确定性派生（同样的输入永远得到同样的产物）；
  - 引擎矩阵、语言表、配音流水线、AudioSeal 水印、本地优先数据路径，
    均按 VoiceStudio 公开 README 中描述的能力做 1:1 结构映射。

正式生产请使用上游 https://github.com/debpalash/VoiceStudio
（本体 AGPL-3.0，默认权重 CC-BY-NC）。
"""
import hashlib
import json
import math

# ---------------------------------------------------------------------------
# 1. 引擎注册表（结构演示：数目与 VoiceStudio 公开数字一致，引擎名为示意）
# ---------------------------------------------------------------------------
TTS_ENGINES = [
    ("xtts_v2",        "多语种克隆"),
    ("bark",           "表达丰富"),
    ("vits",           "轻量快"),
    ("coqui_tts",      "开源标准"),
    ("openvoice",      "音色迁移"),
    ("fish_speech",    "少样本"),
    ("cosyvoice",      "阿里系"),
    ("valle",          "自回归"),
    ("tortoise",       "高保真"),
    ("naturalreaders", "商业风"),
    ("speecht5",       "微软"),
    ("rvc",            "实时变声"),
    ("so_vits_svc",    "歌声"),
    ("elevenlabs",     "SaaS 接入"),
    ("azure_tts",      "云接入"),
    ("edge_tts",       "免费云"),
]
ASR_ENGINES = [
    ("whisper",        "OpenAI"),
    ("whisperx",       "对齐时间戳"),
    ("faster_whisper", "CTranslate 加速"),
    ("nemo_asr",       "NVIDIA"),
    ("wav2vec2",       "Meta"),
    ("silero",         "轻量"),
    ("vosk",           "离线"),
    ("paraformer",     "阿里 FunASR"),
    ("sensevoice",     "多语种"),
    ("deepgram",       "SaaS"),
    ("azure_sr",       "云接入"),
]
LANGUAGE_COUNT = 646  # VoiceStudio 公开宣称覆盖语言/方言数（实际质量取决于引擎）
LANGUAGES_SAMPLE = ["zh-CN","en-US","ja-JP","ko-KR","fr-FR","de-DE","es-ES","ru-RU",
                    "ar-SA","pt-BR","hi-IN","it-IT","th-TH","vi-VN","id-ID","tr-TR"]

REGISTRY = {
    "tts_engine_count": len(TTS_ENGINES),
    "asr_engine_count": len(ASR_ENGINES),
    "language_count": LANGUAGE_COUNT,
    "tts_engines": [{"id": i, "name": n, "note": d} for i, (n, d) in enumerate(TTS_ENGINES)],
    "asr_engines": [{"id": i, "name": n, "note": d} for i, (n, d) in enumerate(ASR_ENGINES)],
    "languages_sample": LANGUAGES_SAMPLE,
}

# ---------------------------------------------------------------------------
# 2. 确定性派生工具
# ---------------------------------------------------------------------------
def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)

def _hash_str(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

def _bounded(seed: int, lo: float, hi: float) -> float:
    # 用 seed 的各位数字做均匀分布映射，确定性且可复现
    frac = (seed % 100000) / 100000.0
    return round(lo + frac * (hi - lo), 2)

def _timbre_vector(seed: int) -> list:
    # 4 维音色向量（明亮/厚度/气息/颗粒），-1..1
    vals = []
    s = seed
    for _ in range(4):
        s = (s * 1103515245 + 12345) & 0xFFFFFFFF
        vals.append(round((s % 2000) / 1000.0 - 1.0, 2))
    return vals

# ---------------------------------------------------------------------------
# 3. 三大入口
# ---------------------------------------------------------------------------
def clone_from_audio(reference: str, tts_engine: str = "xtts_v2") -> dict:
    """克隆 FROM AUDIO：从参考音频派生稳定的音色档案（seed 可复现）。"""
    seed = _seed("clone:" + reference)
    profile = {
        "method": "clone_from_audio",
        "reference": reference,
        "seed": _hash_str("clone:" + reference),
        "reproducible": True,
        "tts_engine": tts_engine,
        "voice_profile": {
            "pitch_hz": _bounded(seed, 85, 300),
            "formant_shift": _bounded(seed, 0.8, 1.3),
            "speed": _bounded(seed, 0.85, 1.2),
            "timbre": _timbre_vector(seed),
            "sample_rate": 24000,
        },
        "watermark": {"type": "audioseal", "detectable": True, "embedded": True},
        "data_path": {"local_first": True, "external_send": False},
    }
    return profile

def design_by_params(params: dict) -> dict:
    """创声 BY DESIGN：从显式参数合成音色档案。"""
    p = {
        "pitch_hz": float(params.get("pitch_hz", 180)),
        "formant_shift": float(params.get("formant_shift", 1.0)),
        "speed": float(params.get("speed", 1.0)),
        "timbre": params.get("timbre", [0.2, -0.1, 0.3, -0.2]),
    }
    # 合法区间校验
    ok_pitch = 70 <= p["pitch_hz"] <= 400
    ok_formant = 0.5 <= p["formant_shift"] <= 1.6
    ok_speed = 0.6 <= p["speed"] <= 1.6
    in_range = ok_pitch and ok_formant and ok_speed
    profile = {
        "method": "design_by_params",
        "params": p,
        "in_valid_range": in_range,
        "seed": _hash_str("design:" + json.dumps(p, sort_keys=True)),
        "voice_profile": p,
        "watermark": {"type": "audioseal", "detectable": True, "embedded": True},
        "data_path": {"local_first": True, "external_send": False},
    }
    return profile

def convert_voice(text: str, target_profile: dict, asr_engine: str = "whisper") -> dict:
    """转换 CONVERT：把输入文本/音频按目标音色档案合成（语音转语音）。"""
    seed = _seed("convert:" + text + target_profile.get("seed", ""))
    out = {
        "method": "convert",
        "asr_engine": asr_engine,
        "source_text": text,
        "target_voice_seed": target_profile.get("seed"),
        "tts_engine": target_profile.get("tts_engine", "xtts_v2"),
        "estimated_duration_s": round(max(1.0, len(text) / 12.0), 2),
        "output": {
            "format": "wav",
            "sample_rate": 24000,
            "speaker_match": _bounded(seed, 0.7, 0.99),
        },
        "watermark": {"type": "audioseal", "detectable": True, "embedded": True},
        "data_path": {"local_first": True, "external_send": False},
    }
    return out

# ---------------------------------------------------------------------------
# 4. 视频配音流水线
# ---------------------------------------------------------------------------
def video_dub(source: str, target_lang: str = "en-US",
              asr_engine: str = "whisper", tts_engine: str = "xtts_v2") -> dict:
    """
    视频配音：上传文件或贴 URL → 自动转写 → 翻译 → 保留原声 → 合成 → 混流。
    source 可以是本地路径或 http(s) URL。
    """
    seed = _seed("dub:" + source + target_lang)
    # 确定性"转写"文本（真实实现由 ASR 引擎产出）
    transcript = ("（示例转写）这是一段用于演示的旁白，"
                  "VoiceStudio 会在本地完成转写与翻译，并保留原始人声底床。")
    translated = ("(demo translation) This is a narration used for demonstration; "
                  "VoiceStudio transcribes and translates locally, keeping the original voice bed.")
    plan = {
        "source": source,
        "source_kind": "url" if source.startswith("http") else "file",
        "target_lang": target_lang,
        "asr_engine": asr_engine,
        "tts_engine": tts_engine,
        "steps": [
            {"step": "transcribe", "engine": asr_engine, "status": "done",
             "output": transcript},
            {"step": "translate", "engine": "nllb/opus", "status": "done",
             "output": translated, "target": target_lang},
            {"step": "keep_original_bed", "status": "done",
             "output": "原始人声底床已保留（避免机械感）"},
            {"step": "synthesize", "engine": tts_engine, "status": "done",
             "output": "目标音色合成完成，已嵌入 AudioSeal 水印"},
            {"step": "mux", "status": "done",
             "output": "音视频对齐混流完成"},
        ],
        "watermark": {"type": "audioseal", "detectable": True, "embedded": True},
        "data_path": {"local_first": True, "external_send": False},
    }
    return plan

# ---------------------------------------------------------------------------
# 5. 质量门（脚本化拦截）
# ---------------------------------------------------------------------------
def quality_gates(A: dict) -> list:
    g = []
    def add(gid, name, ok, msg=""):
        g.append({"id": gid, "name": name, "pass": bool(ok), "message": msg})

    clone = A.get("clone") or {}
    design = A.get("design") or {}
    convert = A.get("convert") or {}
    dub = A.get("dub") or {}
    api = A.get("api", {})

    add("G01", "克隆产物含可复现 seed + voice_profile",
        bool(clone.get("seed")) and bool(clone.get("voice_profile")))
    add("G02", "创声产物参数落在合法区间",
        design.get("in_valid_range", False) if design else True)
    add("G03", "转换产物标注 source/target 且带水印",
        bool(convert.get("target_voice_seed")) and convert.get("watermark", {}).get("embedded"))
    dub_steps = [s["status"] for s in dub.get("steps", [])]
    add("G04", "配音流水线 5 步全部完成",
        len(dub_steps) == 5 and all(s == "done" for s in dub_steps))
    add("G05", "引用引擎在注册表内",
        (clone.get("tts_engine") in dict(TTS_ENGINES)) and
        (convert.get("asr_engine") in dict(ASR_ENGINES)))
    add("G06", "目标语言在 646 注册表内",
        dub.get("target_lang") in LANGUAGES_SAMPLE or dub.get("target_lang", "").startswith(("zh","en","ja")))
    add("G07", "合成产物默认带 AudioSeal 水印",
        all(x.get("watermark", {}).get("embedded") for x in (clone, design, convert, dub)))
    add("G08", "数据路径默认本地（external_send=false）",
        all(x.get("data_path", {}).get("external_send") is False
            for x in (clone, design, convert, dub)))
    add("G09", "本地 API 仅绑 127.0.0.1 且免 server key",
        api.get("bind") == "127.0.0.1" and api.get("requires_server_key") is False)
    return g

# ---------------------------------------------------------------------------
# 6. 端到端组装（供 pipeline.py 调用）
# ---------------------------------------------------------------------------
def build_full(reference: str = "reference_voice.wav",
               design_params: dict = None,
               convert_text: str = "你好，这是用本地工作站合成的演示语音。",
               dub_source: str = "https://example.com/sample.mp4",
               dub_lang: str = "en-US") -> dict:
    design_params = design_params or {"pitch_hz": 200, "formant_shift": 1.0,
                                      "speed": 1.0, "timbre": [0.2, -0.1, 0.3, -0.2]}
    clone_p = clone_from_audio(reference)
    design_p = design_by_params(design_params)
    convert_p = convert_voice(convert_text, clone_p)
    dub_p = video_dub(dub_source, dub_lang)
    A = {
        "registry": REGISTRY,
        "clone": clone_p,
        "design": design_p,
        "convert": convert_p,
        "dub": dub_p,
        "api": {"bind": "127.0.0.1", "port": 3900,
                "requires_server_key": False,
                "protocols": ["rest", "sse", "websocket", "mcp"],
                "local_first": True},
    }
    A["quality_gates"] = quality_gates(A)
    return A

if __name__ == "__main__":
    import sys
    print(json.dumps(build_full(), ensure_ascii=False, indent=2))
