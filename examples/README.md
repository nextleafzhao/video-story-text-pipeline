# examples — 最小可跑样本

本目录只放小样本，不放成品交付稿。

## 用假 OCR 数据跑通 build

```powershell
copy examples\segments.json config\segments.json
copy examples\assemble.json config\assemble.json
mkdir work\ocr
copy examples\ocr\01_intro.jsonl work\ocr\01_intro.jsonl
python -m src.cli build 01_intro
python -m src.cli assemble main
```

如果只想验证 `build`：

```powershell
python -m src.cli build 01_intro
# 产出：work/txt/draft/01_intro_示例段落.txt
```

## 抽帧任务示例

`frames.example.json` 是 `tools.batch_frames` 的输入格式：

```powershell
python -m tools.batch_frames examples\frames.example.json
```

## 7.2 参考配置

`legacy-7.2/segments.json` 是从原 7.2 项目提取的 56 段清单，用于续接或对照；
视频文件不随仓库分发。实际使用时复制到 `config/segments.json` 并按本地路径修改
`config/pipeline.json` 的 `video_dirs`。