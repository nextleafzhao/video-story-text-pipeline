# 工作流

本文件给 agent 和人类共用：每一步写清输入、输出、命令与成功判据。
命令统一从仓库根目录执行，使用 `python -m src.cli`。

## 阶段总览

```
视频 mp4
  → work/raw/<key>/*.raw          抽帧 + 四路裁切
  → work/ocr/<key>.jsonl          逐帧 OCR
  → 时间线（内存）                  merge：去重、回声、姓名/正文拆分
  → work/txt/draft/<key>_<title>.txt   build：通用清洗
  → work/txt/final/<key>_<title>.txt   align：与 wiki 逐句对齐（有剧本页时）
  → 交付 md                        assemble：main / side / supplement
```

`align` 不是必走步骤：有 wiki 页的段走 `align`，没有的段走 `build`。
`assemble` 默认读 `work/txt/final`，缺失时回退 `work/txt/draft` 并告警。

## 0. 自检

```powershell
python -m src.cli doctor
```

- 输入：无。
- 输出：`work/reports/doctor.json`。
- 通过：退出码 0；`python`、`ffmpeg`、`work`、四个配置全部 OK。
- 依赖缺失只报告，不自动安装；按 `README.md` 处理。

## 1. 抽帧 + OCR

```powershell
python -m src.cli run 01_intro          # 示例 key，换成实际段
python -m src.cli run            # 全部段
```

- 输入：`config/segments.json`、`config/pipeline.json`、视频文件。
- 输出：`work/raw/<key>/`（临时）、`work/ocr/<key>.jsonl`。
- 通过：退出码 0；jsonl 存在且行数接近视频秒数。
- 注意：`run` 对已有 jsonl 会 SKIP；需要重跑时先删除对应 jsonl。

四路裁切：

| 区 | 用途 | 默认尺寸 |
|---|---|---|
| `band` | 姓名带 + 底部字幕 | 1360×230 @ (280,780) |
| `panel` | 左上任务面板 | 620×136 @ (0,224) |
| `opt` | 右下选项条 | 520×130 @ (1140,690) |
| `desc` | 右侧信息浮层 | 700×220 @ (1000,300) |

其他分辨率改 `crop`；气泡/行动面板/浮窗整块采集分别用
`pipeline.json` 的 `bubble`、`map_panel`、`tip_panel`。

## 2. 生成逐段 txt

无 wiki 页的段：

```powershell
python -m src.cli build 01_intro
```

- 输入：`work/ocr/<key>.jsonl`、`config/game_profile.json`（可选）。
- 输出：`work/txt/draft/<key>_<title>.txt`。
- 通过：退出码 0；文件非空；头部有标题、视频名、时长。

有 wiki 页的段：

```powershell
python -m src.cli align 01_intro
```

- 输入：OCR jsonl、`config/segments.json` 的 `wiki` 字段、`work/wiki/json/`、`profiles/corrections*`。
- 输出：`work/txt/final/<key>_<title>.txt`、`work/align/<key>.json`。
- 通过：退出码 0；报告含 `fixes`、`review`、`unmatched`；人工复核 review 项。

特殊分支（由 `game_profile.json` 控制）：

- `bubble_keys`：行动模式头像气泡对话，先跑 `python -m src.acquire.bub_ocr <key> <视频名>`。
- `map_panel_keys`：行动模式右侧任务面板，先跑 `python -m src.acquire.map_ocr <key> <视频名>`。
- `tips_keys`：地图浮窗战报，先跑 `python -m src.acquire.tip_ocr`。

## 3. 逐段检查

```powershell
python -m src.cli check polish
```

- 输入：`work/txt/final/*.txt`（缺失回退 `work/txt/draft`）。
- 输出：`work/reports/scan_polish.json`。
- 通过：退出码 0；issues 为空。
- 检查项：括号平衡、ASCII 混入、残留符号、过短画面文字、10 秒内近似重复。

## 4. 拼装交付稿

```powershell
python -m src.cli assemble main
python -m src.cli assemble side
python -m src.cli assemble supplement
python -m src.cli assemble all
```

- 输入：`config/assemble.json`、逐段 txt。
- 输出：配置中 `file` 指定的 Markdown（默认 `transcript.md`）。
- 通过：退出码 0；没有 `MISSING`。
- `side` / `supplement` 默认关闭，`enabled=true` 才生成。

## 5. 交付门禁

```powershell
python -m src.cli check status
python -m src.cli check recheck
```

- `status`：交付稿关键词、单双字画面文字、括号、ASCII、10 秒重复。
- `recheck`：破字、括号、省略号独白、观察短语。
- 通过：退出码 0；issues 为空。
- **只扫 `work/txt` 不够，最终以交付 md 的扫描结果为准。**

## 增量与重跑

- 已交付段按只读快照处理，不随手重跑。
- 必须重跑时先做影子 diff：旧文件备份到 `work/txt/final.bak/<key>_*.txt`，再比较新增/删除行。
- 连续 wiki 剧本的段共享游标：`config/game_profile.json` 的 `align_cursor_keys` 与
  `align_cursor_wikis`，游标存 `work/align/cursor.json`。
- 新增段只跑该段，不要为了“统一”重跑全部。

## 失败处理

| 现象 | 优先检查 |
|---|---|
| `FFMPEG FAIL` | `pipeline.ffmpeg` 路径、视频文件是否存在 |
| `decode failed: got 0 bytes` | 时间点是否超过视频长度 |
| `MISSING <key>` | `work/ocr/<key>.jsonl` 是否存在、`segments.json` 的 key |
| OCR 很慢 | `ocr.workers` / `ocr.scale`；CPU 线程 |
| 对齐 review 多 | 段是否配错 `wiki`、`corrections` 是否需要补 |
| `check` 有 QUOTE | 引号补全规则或原件，抽帧确认后再改 |