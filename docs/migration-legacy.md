# 续接旧项目数据

原项目把产物放在 `.work/` 下；新项目统一到 `work/` 与 `profiles/`。
`tools/migrate_legacy.py` 负责复制，不移动原文件。

## 映射

| 旧路径 | 新路径 |
|---|---|
| `.work/ocr/` | `work/ocr/` |
| `.work/txt/` | `work/txt/draft/` |
| `.work/txt2/` | `work/txt/final/` |
| `.work/align/` | `work/align/` |
| `.work/bub/` | `work/bub/` |
| `.work/map/` | `work/map/` |
| `.work/frames/` | `work/frames/` |
| `.work/BWiki/json/` | `work/wiki/json/` |
| `.work/BWiki/raw/` | `work/wiki/raw/` |
| `.work/corrections.json` | `profiles/corrections.json` |
| `.work/corrections.d/` | `profiles/corrections.d/` |
| `.work/names_extra.json` | `profiles/names_extra.json` |
| `.work/screen_drop.json` | `profiles/screen_drop.json` |
| `.work/speaker_drop.json` | `profiles/speaker_drop.json` |
| `.work/name_unknown.json` | `profiles/name_unknown.json` |

视频、成品 md、`raw/` 帧、测试用 raw/jsonl/图片、`.tmp/` 不复制。

## 命令

```powershell
# 先看计划
python -m src.cli migrate --source "C:/path/to/旧项目" --dry-run

# 执行；默认不覆盖已有文件
python -m src.cli migrate --source "C:/path/to/旧项目"

# 需要覆盖时
python -m src.cli migrate --source "C:/path/to/旧项目" --force
```

`--source` 可以指向项目根，也可以直接指向 `.work/`。
报告写到 `work/reports/migrate_legacy.json`。

## 迁移后

```powershell
python -m src.cli doctor
python -m src.cli check config
```

- 检查 `config/segments.json` 是否与本地视频对应；7.2 的 56 段清单可参考
  `examples/legacy-7.2/segments.json`。
- `work/txt/final` 有旧产物时，`assemble` 会优先使用；旧段不重跑。
- 旧 `corrections` 已原样进入 `profiles/`，`align` 会直接读取。
- 如果旧项目使用了 `BWiki/json`，迁移后 `align` 读取 `work/wiki/json`，路径已对齐。

## 注意

- 迁移只复制数据，不校验内容；跑一次 `check` 再继续。
- 旧稿可能含当时未修正的问题；按“已交付段只读”原则，不要为了统一格式重跑。