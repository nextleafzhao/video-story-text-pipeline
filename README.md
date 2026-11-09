# Video Story Text Pipeline

把**原神剧情录屏**转成结构化 Markdown 剧情文本。第一信源是画面内嵌字幕与界面文字，
**只做 OCR，不做语音识别（无 ASR / LLM / TTS）**。

## 适用

- 原神主线、支线、活动、聚所的剧情录屏。
- 默认按 1920×1080 布局裁切；其他分辨率改 `config/pipeline.json` 的 `crop`。
- 面向 wiki 词条建立/维护的同事，以及他们各自的 agent。

## 快速开始

```powershell
# 1. 环境：Python 3.9+，系统安装 ffmpeg 并加入 PATH
pip install -r requirements.txt

# 2. 配置：可先用 .example 冒烟；正式跑时复制模板并按实际视频修改
cd config
copy pipeline.json.example pipeline.json
copy segments.json.example segments.json
copy game_profile.json.example game_profile.json
copy assemble.json.example assemble.json
cd ..

# 3. 自检
python -m src.cli doctor

# 4. 跑一段：抽帧 + OCR
python -m src.cli run 01_intro

# 5. 清洗：无 wiki 页走 build，有 wiki 页走 align
python -m src.cli build 01_intro
python -m src.cli align 01_intro

# 6. 检查 + 拼装
python -m src.cli check polish
python -m src.cli assemble main
python -m src.cli check status
```

## 目录

```
AGENTS.md          agent 行为规范与执行入口
README.md          人类入口
config/            pipeline / segments / game_profile / assemble + JSON Schema
profiles/          经验资产：人工修正、白名单、过滤名单（原样保留）
src/               流水线代码（acquire / merge / align / build / checks）
tools/             抽帧核对、放大、批量抽帧、监听、旧数据迁移
docs/              workflow / pitfalls / quality / data-format / migration
examples/          小样本，供冒烟与上手；不放成品
work/              运行时产物（gitignore）
```

## 经验资产

`profiles/` 保存实践验证过的人工修正、角色名映射、过滤名单；初始数据来自 7.2 项目，作为经验来源示例，不是通用默认。
`config/game_profile.json.example` 保存错字表、说话人变体、UI 词表、面板段 key。
这些是劳动成果，新增段时按同样格式追加，不要删。

## 续接旧数据

原项目的 `.work/` 可以迁到新布局：

```powershell
python -m src.cli migrate --source "旧项目路径" --dry-run
python -m src.cli migrate --source "旧项目路径"
```

映射见 `docs/migration-legacy.md`。视频、成品 md、raw 帧不会被复制。

## 质量检查

```powershell
python -m src.cli check config    # 四个配置是否合法、arcs 是否引用存在的段
python -m src.cli check polish    # 逐段：括号、ASCII、符号、过短画面文字、近似重复
python -m src.cli check status    # 交付稿：关键词、短句、括号、ASCII、10 秒重复
python -m src.cli check recheck   # 交付稿：破字、括号、省略号独白、观察短语
```

每次命令都会写 `work/reports/<command>.json`，退出码 0 表示通过。