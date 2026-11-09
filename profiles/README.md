# profiles — 经验资产

本目录保存实践中积累的人工修正与白名单数据，初始数据来自 7.2 项目，作为经验来源示例，**原样保留**。
新增段或新活动时可以按同样的格式继续追加，不需要改代码。

| 文件 | 内容 | 读取方 |
|---|---|---|
| `corrections.json` | 全局人工修正，按段 key 分组 | `src/align/align.py` |
| `corrections.d/<key>.json` | 单段人工修正 | `src/align/align.py` |
| `names_extra.json` | 说话人白名单补充（OCR 认不全的角色名） | `src/build/build_txt.py` |
| `screen_drop.json` | 按段过滤选项/浮窗文本（地图标签、UI 残片等） | `src/align/align.py` |
| `speaker_drop.json` | 按段把误判的“姓名”降级为画面文字 | `src/align/align.py` |
| `name_unknown.json` | 按段把说话人显示为 `???` | `src/align/align.py` |
| `game_profile.7.2.json` | 7.2 的段 key/观察词示例，按项目合并到 `config/game_profile.json` | 人工参考 |

## 修正格式

`corrections.json`：

```json
{
  "01_hm1": [
    {"t": 123, "find": "原文片段", "repl": "替换后"},
    {"t": 456, "find": "OCR 误识名字", "repl": "正确名字", "field": "name"}
  ]
}
```

`corrections.d/<key>.json` 直接是数组，不需要外层 key：

```json
[
  {"t": 123, "find": "原文片段", "repl": "替换后"}
]
```

可选字段：

- `field`：`body`（默认）或 `name`。
- `kind`：`line`（默认两者都匹配）、`screen`。
- `name`：正文替换的同时把说话人改成该值。

## 注意事项

- 时间是该句首次出现的时间（秒），匹配窗口为 ±3 秒。
- `screen_drop.json` 用于选项/浮窗文本过滤；画面文字本身以“宁多录不漏录”为准，不据它整条丢弃。
- 这些文件缺失时管线会降级运行，不会崩溃；但人工修正的效果会消失。