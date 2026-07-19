# 使用示例

## 场景 1：早上开始工作

**用户说：** "显示今天的天气和待办"

**Agent 执行：**

```bash
# 1. 天气 → top-left
python scripts/widget.py weather --slot top-left --data-stdin <<EOF
{"location":"青岛","current":{"temp":"26","feels":"28","humidity":"71","condition":"多云"}}
EOF

# 2. 待办 → bottom
python scripts/widget.py todo --slot bottom --data-stdin <<EOF
{"title":"今天","items":[{"text":"整理图表","tag":"today"},{"text":"写文档","tag":"today"}]}
EOF
```

**输出：** 两个 JSON payload（dry-run），用户确认后加 `--push`。

---

## 场景 2：深度工作前推专注卡片

**用户说：** "推送一张专注卡片，任务'完成论文结果章节'，副标题'只处理正文和图表'"

**Agent 执行：**

```bash
python scripts/widget.py focus --slot middle --data-stdin --push <<EOF
{"task":"完成论文结果章节","big_text":"专注","subtitle":"只处理正文和图表","tag":"today"}
EOF
```

**输出：** `{"status":"ok","slot":"middle"}` — Kindle 屏幕显示专注卡片。

---

## 场景 3：推完卡片后看完整效果

**用户说：** "给我看看现在 Kindle 上会显示什么"

**Agent 执行：**

```bash
python scripts/widget.py --preview
```

**输出：** `kindledesk-preview.png` — 本地 PNG 预览，不推送、不修改缓存。

---

## 场景 4：从笔记随机抽反思

**用户说：** "从笔记里随机抽一条反思推送到 Kindle"

**Agent 执行：**

```bash
python scripts/widget.py reflection --slot middle --from-notes --push
```

**输出：** 随机抽取一条反问 → 推送 → Kindle 显示。

---

## 场景 5：清理和重新布局

**用户说：** "先清掉 Kindle 上所有卡片，然后重新布置：天气左上、AI 状态右上、待办底部"

**Agent 执行：**

```bash
# 清空
python scripts/widget.py --clear

# 重新布置
python scripts/widget.py weather --slot top-left --data-stdin --push <<EOF
{"location":"青岛","current":{"temp":"26","feels":"28","humidity":"71","condition":"多云"}}
EOF

python scripts/widget.py ai-status --slot top-right --data-stdin --push <<EOF
{"session":"KindleDesk","model":"Codex","task":"实现 Widget 编排"}
EOF

python scripts/widget.py todo --slot bottom --data-stdin --push <<EOF
{"title":"今天","items":[{"text":"整理图表","tag":"today"}]}
EOF
```

---

## 场景 6：已完成任务过滤

**用户说：** "更新待办，'整理图表'已经做完了，'写文档'还在做"

**Agent 执行：**

```bash
python scripts/widget.py todo --slot bottom --data-stdin --push <<EOF
{"title":"今天","items":[
  {"text":"整理图表","tag":"已完成"},
  {"text":"写文档","tag":"today"}
]}
EOF
```

**效果：** daemon 渲染时自动跳过 `tag: "已完成"` 的项，Kindle 上只显示"写文档"。已完成的项留在 JSON 里作为记录，但不占用屏幕空间。