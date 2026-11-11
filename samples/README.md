# 示例数据说明

本 Demo 为**确定性结构演示**，不读取真实音频文件——所有声学参数由输入字符串的哈希派生（同样输入永远得到同样产物）。

- `reference_voice.wav` 仅为示意文件名，真实克隆时替换为你的参考音频路径即可；
- `pipeline.py` 与 `server.py` 会据此文件名确定性地生成可复现的音色档案（seed + pitch/formant/speed/timbre）；
- 视频配音的 `源` 可为本地文件路径或 http(s) URL，同样确定性派生转写/翻译文本。

如需接入真实模型，请参考上游仓库 https://github.com/debpalash/VoiceStudio
（本体 AGPL-3.0，默认权重 CC-BY-NC）。
