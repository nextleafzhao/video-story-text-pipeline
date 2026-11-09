# AGENTS.md

本文件是 agent 在本项目中的行为规范与执行入口，不是可商量的建议。
人类同事也建议先读一遍：它说明了项目怎么跑、每一步的判据、以及哪些事不要做。

## 0. 先读什么

1. 本文件（约束与入口）
2. `README.md`（项目是什么、怎么开始）
3. `docs/workflow.md`（每一步的输入/输出/成功判据）
4. `docs/pitfalls.md`（实践踩坑与经验表）
5. `docs/quality.md`（质量框架与检查清单）

## 1. 项目是什么

把**原神剧情录屏**转成结构化 Markdown 剧情文本。第一信源是画面内嵌字幕与界面文字，
**只做 OCR，不做语音识别（无 ASR / LLM / TTS）**。

- 目标范围：原神剧情录屏（主线、支线、活动、聚所等，以实际录制范围为准）。
- 默认布局：1920×1080；其他分辨率改 `config/pipeline.json` 的 `crop`。
- 交付对象：wiki 词条建立与维护的同事。
- 交付形态：agent-first 仓库。同事克隆后启动自己的 agent，按本文件与 `docs/` 开工。

## 2. 目录地图

| 路径 | 职责 |
|---|---|
| `src/cli.py` | 唯一命令入口 |
| `src/common/` | `paths.py`（唯一 ROOT/WORK）、`config.py`（配置加载）、`report.py`（JSON 报告） |
| `src/acquire/` | 抽帧、OCR、气泡/行动面板/浮窗采集 |
| `src/merge/` | OCR 记录 → 台词时间线 |
| `src/align/` | wiki 抓取/解析、逐句对齐、浮窗/面板解析 |
| `src/build/` | 逐段 txt、主线/支线/补录拼装 |
| `src/checks/` | 配置校验、逐段扫描、交付稿复核 |
| `profiles/` | **经验资产，原样保留**：人工修正、白名单、过滤名单 |
| `config/` | 流程配置（实际 json 不入库，只提交 `.example` 与 schema） |
| `tools/` | 抽帧核对、放大、批量抽帧、监听、旧数据迁移 |
| `examples/` | 小样本，供冒烟与上手；不放成品 |
| `work/` | 运行时产物（gitignore） |

## 3. 标准开工顺序

```powershell
python -m src.cli doctor
python -m src.cli migrate --source "旧项目路径" --dry-run   # 可选，续接旧数据
python -m src.cli run 01_intro          # 示例 key，换成实际段
python -m src.cli build 01_intro        # 无 wiki 页的段
python -m src.cli align 01_intro        # 有 wiki 页的段
python -m src.cli check polish
python -m src.cli assemble main
python -m src.cli check status
python -m src.cli check recheck
```

## 4. 每步判据

| 命令 | 输入 | 输出 | 成功判据 |
|---|---|---|---|
| `doctor` | 无 | `work/reports/doctor.json` | 退出码 0；config/ffmpeg/work 全 OK |
| `run` | 视频 + `segments.json` | `work/raw/`、`work/ocr/<key>.jsonl` | 退出码 0；jsonl 存在且行数合理 |
| `build` | `work/ocr/<key>.jsonl` | `work/txt/draft/<key>_<title>.txt` | 退出码 0；文件非空 |
| `align` | OCR + wiki/screen 配置 | `work/txt/final/`、`work/align/<key>.json` | 退出码 0；fixes/review/unmatched 有报告 |
| `assemble` | `work/txt/final/`（缺失回退 draft） | 根目录交付 md | 退出码 0；无 MISSING |
| `check config` | 四个配置 | `work/reports/validate_config.json` | 退出码 0；issues 为空 |
| `check polish` | 逐段 txt | `work/reports/scan_polish.json` | 退出码 0 |
| `check status` | 交付 md | `work/reports/status.json` | 退出码 0 |
| `check recheck` | 交付 md | `work/reports/recheck.json` | 退出码 0 |

## 5. 行为约束

1. **先思而后动**：先看清用户消息中的指令，再确定执行范围。
2. **只做用户要求做的**：要求以外的事不做；改动必须手术般精确，严控范围。
3. 不要使用 `taskkill /F /IM node.exe`；需要时精准关闭自己启动的进程。
4. 不要使用 `taskkill /F /IM msedge.exe`；需要时只关闭自己启动的浏览器进程。
5. 除非用户明确询问，不要在回答中询问下一步/提供建议；但可以向用户提问以澄清需求。
6. **路径只用 `src.common.paths` 的 `ROOT`/`WORK`**，禁止依赖当前工作目录。
7. **段号、任务名、坐标、UI 词表进 `config/` 或 `profiles/`**，不要写死在通用逻辑里。
8. 配置只改 `*.json` 的实际副本；不要把实际配置提交到仓库（只提交 `.example`）。
9. **已交付段不重跑**；只跑用户指定的 key。重跑前先做影子 diff。
10. **交付前必须跑 `check`**；只扫 `work/txt` 不够，最终以交付 md 的扫描结果为准。
11. 不要把本地绝对路径、账号、token、cookie 等隐私/密钥写入仓库；领域专名保留是正常且必要的。
12. 经验资产（`profiles/`、`docs/pitfalls.md` 的错字表与说话人变体）**不得以“精简”为由删除**。

## 6. 停点

- 每段 OCR、对齐、交付后，给出核对材料：抽帧 PNG、txt 路径、check 报告。
- **是否继续由使用者决定**；agent 不预设“跑完整条流水线”，也不预设人机节奏。
- 环境缺失先跑 `doctor`，按 `README.md` 安装；不要擅自改系统配置。

## 7. 质量框架

- 原则：确定性优先、可复现、可自校验、分层检查。
- 分层：L0 配置合法 → L1 语法/import → L2 冒烟 → L3 交付门禁。
- 实现见 `src/checks/`；说明见 `docs/quality.md`。
- 质量不追求一次到位，靠后续实践反馈迭代；但每次新增规则必须落到脚本或配置。