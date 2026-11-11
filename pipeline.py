#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoiceStudio Mini · headless pipeline
====================================
不依赖任何真实音频/模型，确定性地把"一部参考音频 + 一段文本 + 一个视频源"
跑完 VoiceStudio 的全部关键产物，并落盘为可直接审阅的 JSON，最后跑质量门。

用法：  python3 pipeline.py
产物：  output/registry.json  output/clone.json  output/design.json
        output/convert.json  output/dub.json  output/api.json
        output/quality_gates.json  output/manifest.json
"""
import json
import os
import sys

import core

OUT = os.path.join(os.path.dirname(__file__), "output")


def write_json(name, obj):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    A = core.build_full(
        reference="reference_voice.wav",
        design_params={"pitch_hz": 200, "formant_shift": 1.0, "speed": 1.0,
                       "timbre": [0.2, -0.1, 0.3, -0.2]},
        convert_text="你好，这是用本地工作站合成的演示语音。",
        dub_source="https://example.com/sample.mp4",
        dub_lang="en-US",
    )

    files = {
        "registry.json": A["registry"],
        "clone.json": A["clone"],
        "design.json": A["design"],
        "convert.json": A["convert"],
        "dub.json": A["dub"],
        "api.json": A["api"],
    }
    written = [write_json(n, o) for n, o in files.items()]
    gpath = write_json("quality_gates.json", {"quality_gates": A["quality_gates"]})

    total = len(A["quality_gates"])
    passed = sum(1 for g in A["quality_gates"] if g["pass"])
    manifest = {
        "project": "VoiceStudio Mini",
        "inspired_by": "https://github.com/debpalash/VoiceStudio",
        "deterministic": True,
        "files": [os.path.basename(p) for p in written] + [os.path.basename(gpath)],
        "quality_gates": {"passed": passed, "total": total},
    }
    write_json("manifest.json", manifest)

    print("=" * 56)
    print("VoiceStudio Mini · 管线运行完成（确定性，无需 GPU）")
    print("=" * 56)
    print(f"  引擎注册表 : {A['registry']['tts_engine_count']} TTS / "
          f"{A['registry']['asr_engine_count']} ASR / "
          f"{A['registry']['language_count']} 语言")
    print(f"  克隆 seed  : {A['clone']['seed']}  (可复现)")
    print(f"  配音步骤   : {len(A['dub']['steps'])} 步全部 {A['dub']['steps'][0]['status']}")
    print(f"  本地 API   : {A['api']['bind']}:{A['api']['port']} "
          f"免key={not A['api']['requires_server_key']} {A['api']['protocols']}")
    print("-" * 56)
    for g in A["quality_gates"]:
        mark = "PASS" if g["pass"] else "FAIL"
        print(f"  [{mark}] {g['id']} {g['name']}")
    print("-" * 56)
    print(f"  质量门 : {passed}/{total} 通过")
    print(f"  产物目录 : {OUT}")
    if passed != total:
        print("  警告：存在未通过质量门，产物未达交付标准。")
        return 1
    print("  全部质量门通过，产物可交付。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
