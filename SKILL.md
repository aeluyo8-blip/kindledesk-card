---
name: kindledesk-card
description: 为 KindleDesk 的 600×800 Kindle 墨水屏选择并推送 widget。用户提到 Kindle 卡片、墨水屏副屏、桌面卡片、待办、专注任务、日程、消息简报或要求预览/推送时使用。默认只校验/输出 payload，只有用户明确说"推送、发送到 Kindle、现在显示"时才 POST /widget。
trigger_keywords:
  - Kindle 卡片
  - 墨水屏
  - 副屏
  - 桌面卡片
  - 待办卡片
  - 专注任务
  - 推送卡片
  - 发送到 Kindle
  - 现在显示
  - 推送到 Kindle
  - widget 卡片
allowed-tools:
  - Bash
  - Read
  - Write
---

# KindleDesk Widget 卡片

KindleDesk 是一套 Widget 系统，把越狱 Kindle 变成 AI 驱动的墨水屏副屏。你说"显示今天的天气和待办"，Agent 选 type + slot + data，dry-run 校验，确认后推送到 Kindle。

PC daemon 把 1-4 个 widget 按 2-1-1 网格组合成一张 600×800 的灰阶图片，再通过 Wi-Fi 推送到 Kindle 的 `/dev/fb0`。

## 布局

```text
┌────────────┬────────────┐
│ top-left   │ top-right  │   25 px 以上留给 Kindle 系统时间
├────────────┴────────────┤   不在右上角重复显示时间
│         middle          │   不显示 pushed / KindleDesk 等技术性页脚
├─────────────────────────┤
│         bottom          │
└─────────────────────────┘
```

`full` 会覆盖其它所有 slot。

## 选位规则

按优先级决定 slot：

1. 用户明确指定了位置 → 用指定的。
2. 最重要的单一信息 → `middle`（最宽）。
3. 两个并列的 glance 信息 → `top-left` + `top-right`。
4. 列表/多行详情 → `bottom`。
5. 用户只想全屏展示一句话/一段内容 → `full`。

默认组合（用户无意见时）：

```text
top-left  = weather    top-right = ai-status
middle    = focus      bottom    = todo
```

## Widget 类型与数据

| type | 用途 | 必要字段 | 推荐 slot |
|---|---|---|---|
| `weather` | 天气 | `location`, `current: {temp, feels, humidity, condition}` | top-left / top-right |
| `clock` | 当前时间 | 无 | top-right |
| `focus` | 当前唯一重点任务 | `task`, 可选 `big_text`, `subtitle`, `tag` | middle |
| `todo` | 待办列表 | `title`, `items: [{text, tag?}]` | bottom |
| `ai-status` | AI 当前会话状态 | `task`, 可选 `session`, `model` | top-right |
| `scratch` | 自由文本/便签 | `title`, `text` | full / middle |
| `calendar` | 日程 | `title`, `events: [{time, title}]` | middle / bottom |
| `quote` | 每日一句/书摘 | `text` 或 `quote`, 可选 `author`, `source` | top-left / middle |
| `reading` | 当前阅读进度 | `title`, `progress_pct`, 可选 `author`, `streak_days`, `today_min` | middle / bottom |
| `system` | PC 系统状态 | `cpu_pct`, `memory_pct`, `disk_pct`, `battery_pct` 任选 | top-left / top-right |
| `countdown` | 事件倒计时 | `remaining`, 可选 `label`, `target` | middle |
| `inbox` | 未读消息汇总 | `total`, `sources: [{name, count}]` | top-right / bottom |
| `reflection` | 自问/反思 | `question`, 可选 `category`, `hint` | middle / full |

### Disambiguation — 常见混淆

| 场景 | 用这个 | 不用那个 | 原因 |
|---|---|---|---|
| 今天要做的几件事 | `todo` | `focus` | focus 只放一件事，todo 放列表 |
| 当前唯一在做的事 | `focus` | `todo` | 一件任务用 focus，醒目且可加副标题 |
| 随手记一句话 | `scratch` | `reflection` | scratch 是便签，reflection 是反问/反思 |
| 今天的日程 | `calendar` | `todo` | calendar 有时间点，todo 没有 |
| AI 在做什么 | `ai-status` | `focus` | ai-status 是汇报 AI 状态，focus 是人的任务 |
| 一句话名言/书摘 | `quote` | `scratch` | quote 有 author/source 字段，排版不同 |
| 电脑 CPU/内存 | `system` | `weather` | system 是系统指标，weather 是天气 |
| 倒计时几天 | `countdown` | `calendar` | countdown 是距某个日期的剩余天数 |
| 消息数量统计 | `inbox` | `todo` | inbox 是未读计数，不是待办事项 |

### 数据示例

```json
// weather
{"location":"青岛","current":{"temp":"26","feels":"28","humidity":"71","condition":"多云"}}

// clock
{}

// focus
{"tag":"today","task":"完成论文结果章节","big_text":"专注","subtitle":"只处理正文和图表"}

// todo — tag: "已完成" 的 item 不会被渲染
{"title":"今天","items":[{"text":"整理图表","tag":"today"},{"text":"已完成项","tag":"已完成"}]}

// ai-status
{"session":"KindleDesk","model":"Codex","task":"实现 Widget 编排"}

// scratch
{"title":"便签","text":"3pm 见 Bob — 带上昨天那张设计稿"}

// calendar
{"title":"今天","events":[{"time":"09:30","title":"项目同步"},{"time":"14:00","title":"设计评审"}]}

// quote
{"text":"先完成，再完善。","author":"杰哥","source":"2-mainNotes"}

// reading
{"title":"认知觉醒","author":"周岭","progress_pct":72,"streak_days":5,"today_min":35}

// system
{"cpu_pct":42,"memory_pct":63,"disk_pct":81,"battery_pct":88}

// countdown
{"label":"论文提交","remaining":"还剩 12 天","target":"2026-08-01"}

// inbox
{"total":8,"sources":[{"name":"微信","count":5},{"name":"邮件","count":3}]}

// reflection
{"question":"我现在做的事是不是在逃避更重要的事？","category":"方向类","hint":"停下来，诚实回答"}
```

## 操作流程

1. 把用户内容压缩成可扫读的短句，不擅自补充事实。
2. 根据信息结构选择 `type` + `slot` + `data`。
3. **默认行为是 dry-run**：运行脚本并输出校验后的 JSON payload，不接触 Kindle。
4. 只有当用户当前请求中明确说"推送、发送到 Kindle、现在显示、推过去"等时，才加 `--push`。
5. 推送前，如果目标 slot 已被占用，先询问用户是否覆盖；不要擅自 `--force` 覆盖。

## 什么时候该推，什么时候不该推

### 该推
- 用户明确要求推送
- 开始一个非 trivial 任务时（推 `ai-status` 告知当前任务）
- 长时间任务完成时（推 `scratch` 告知结果）

### 不该推
- 用户只是问"Kindle 怎么越狱"——这是技术问答，不是卡片操作
- 用户只是讨论/规划卡片内容，没说要推送
- 用户说"给我看看效果"——用 `--preview`，不推送
- 每次工具调用都推——墨水屏刷新有寿命，e-ink 不适合高频刷新
- 用户没有明确提到 Kindle/卡片/副屏/推送——不要主动关联

## 命令

### 环境变量

脚本依赖以下环境变量，未设置时使用默认值：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `KINDLEDESK_URL` | `http://127.0.0.1:8000` | daemon 地址 |
| `KINDLEDESK_SKILL_ROOT` | 脚本自动检测 | Skill 安装目录 |
| `KINDLEDESK_NOTES_VAULT` | `D:\大学\note` | Obsidian vault 路径（reflection --from-notes 用） |
| `OBSIDIAN_VAULT` | — | 与上一条等效，兼容 Obsidian 用户习惯 |

### 命令示例

> 以下命令中 `$KINDLEDESK_SKILL_ROOT` 是 Skill 安装目录。首次使用前设置环境变量或替换为实际路径。

输出/校验 payload（默认）：

```bash
python $KINDLEDESK_SKILL_ROOT/scripts/widget.py focus \
  --slot middle --data-stdin
```

stdin 里跟 JSON：

```json
{"task":"完成论文结果章节","big_text":"专注","subtitle":"只处理正文和图表"}
```

渲染当前 daemon 快照为 PNG（不推送，不修改缓存）：

```bash
python $KINDLEDESK_SKILL_ROOT/scripts/widget.py --preview
```

明确确认后的推送（会调用一次 `POST /widget`）：

```bash
python $KINDLEDESK_SKILL_ROOT/scripts/widget.py focus \
  --slot middle --data-stdin --push
```

清理 slot：

```bash
python $KINDLEDESK_SKILL_ROOT/scripts/widget.py --clear --slot middle
```

### reflection 特殊用法：从笔记中随机抽取

`reflection` widget 可以直接从你的 `2-mainNotes/自问清单.md` 里随机抽一条反问：

```bash
python $KINDLEDESK_SKILL_ROOT/scripts/widget.py reflection \
  --slot middle --from-notes --push
```

- 默认读取 `$KINDLEDESK_NOTES_VAULT/2-mainNotes/自问清单.md`；可用 `--from-notes <vault路径>` 覆盖。
- 可用 `--category 方向类` / `--category 行动类` / `--category 觉察类` 限定类别。
- 会自动避免重复上一条刚推过的反问。

## 失败处理

| 失败场景 | 症状 | 处理 |
|---|---|---|
| 校验失败 | widget.py 返回 `validation error: ...` | 检查 type/slot/data 是否符合上表，修正后重试 |
| daemon 不可达 | `KindleDesk daemon unreachable: ...` | 启动 `daemon/serve.py`（在 kindledesk 项目目录下），等 2 秒后重试 |
| slot 被占用 | `slot 'xxx' is occupied. Use --force to overwrite.` | 告知用户目标 slot 已被占用，问是否覆盖；确认后加 `--force` |
| daemon 返回 400 | `400` + 具体字段名 | daemon 的 schema 校验失败，读返回的 error message，修正 data 字段后重试 |
| 推送后 Kindle 无变化 | 状态码 200 但屏幕没变 | daemon 内部有 1.5s 去抖；等 30s 仍无变化，检查 Kindle 端 `fetch_loop` 是否在运行 |
| Kindle 网络不通 | 推送超时 | 不自动切换 USB/SSH，不重启设备；报告用户检查 Wi-Fi 连接 |

## 反例（什么不是这个 Skill 的活）

- "Kindle 怎么越狱？" → 这是技术问答，用知识库回答，不用卡片
- "帮我写一篇论文" → 这是写作任务，不是卡片操作
- "今天天气怎么样？" → 这是查询，不是推送；如果用户接着说"推到 Kindle"才触发
- "给我推荐一本书" → 这是推荐，和卡片无关
- "Kindle 屏幕不亮了怎么办" → 这是排障，不是卡片操作
- "打开/关闭 Kindle 的 Wi-Fi" → 这是设备管理，用 KUAL 菜单，不用卡片