# 质量框架

质量不追求一次到位，而是**确定性优先、可复现、可自校验、分层检查**。
每次新增规则必须落到脚本或配置，不能只写进文档。

## 分层

| 层 | 目标 | 实现 | 通过标准 |
|---|---|---|---|
| L0 配置合法 | 四个配置可解析、字段完整、arcs 引用存在的段 | `src/checks/validate_config.py` | `check config` 退出码 0 |
| L1 语法/import | 所有脚本可编译、模块可导入 | `ast.parse` + `import` | 无 SyntaxError / ImportError |
| L2 冒烟 | 用假 OCR 数据跑通 build → assemble | `examples/` + `tests/test_smoke.py` | pytest 通过、产出 txt 非空 |
| L3 交付门禁 | 逐段与交付稿无结构性瑕疵 | `scan_polish` / `status` / `recheck` | 三个 check 退出码 0 |

## 检查项与脚本映射

| 检查项 | 脚本 | 输入 |
|---|---|---|
| 配置字段/类型/引用 | `check config` | `config/*.json` |
| 括号平衡、ASCII、符号、过短画面文字、近似重复 | `check polish` | `work/txt/final`（回退 draft） |
| 交付稿关键词、单双字、括号、ASCII、10 秒重复 | `check status` | 交付 md |
| 破字、括号、省略号独白、观察短语 | `check recheck` | 交付 md |
| 环境/依赖 | `doctor` | 无 |

## 报告与退出码

每个命令写 `work/reports/<command>.json`，结构：

```json
{
  "step": "scan_polish",
  "ok": false,
  "time": "2026-11-10T12:00:00",
  "issues": [{"key": "01_intro", "line": 42, "tag": "QUOTE", "text": "..."}]
}
```

- `ok=true` 且退出码 0：通过。
- `ok=false` 或退出码非 0：必须处理，不能只看 stdout。

## 规则落地

- 新的错字/替换规则 → `config/game_profile.json` 的 `typo_fix`。
- 新的说话人变体 → `name_fix` 或 `extra_name_whitelist`。
- 新的观察词/教学卡 → `watch_tokens` / `watch_phrases`。
- 新的段级过滤 → `profiles/screen_drop.json` / `speaker_drop.json` / `name_unknown.json`。
- 新的通用检查 → `src/checks/`，并补 `tests/`。

## 当前边界

- 不做完整 CI，先保证本地可执行。
- 不保证所有 OCR 噪声都能自动识别；判断密集的校对仍需人看抽帧。
- 门禁只覆盖结构性问题，语义正确性靠人工复核 + wiki 对齐报告。
- 规则靠实践迭代：每次踩坑后，先把规则写进配置或脚本，再继续下一段。