# KindleDesk 首次接入与连接排障

用于“第一次配置”“KindleDesk 怎么装”“daemon 连不上”“推送成功但 Kindle 不更新”等请求。

目标状态：PC daemon 本机可访问、Kindle KUAL 扩展已安装、`pc_ip` 指向 PC、Kindle 每 60 秒成功拉取 `/fb`。

## 原则

- 先读取状态，再处理第一个不满足项。
- 涉及越狱、安装 `.bin`、开机自启、系统屏保或重启设备时，必须让用户亲自确认和操作。
- 主链路是 Wi-Fi PULL，不为排障自动启用 SSH。
- 不自动推送测试 widget；端到端测试仍需用户明确同意推送。

## 状态探测

先找到 KindleDesk 主项目目录。如果本机没有，指导用户克隆：

```bash
git clone https://github.com/aeluyo8-blip/kindledesk-card.git
```

在项目根目录检查 daemon：

```bash
curl -f http://127.0.0.1:8000/card.png -o /tmp/kindledesk-card.png
curl -f http://127.0.0.1:8000/fb -o /tmp/kindledesk-fb.raw
wc -c /tmp/kindledesk-fb.raw
```

Kindle Basic 3 的 `/fb` 应为 `486400` 字节。Windows PowerShell 使用：

```powershell
curl.exe -f http://127.0.0.1:8000/fb -o "$env:TEMP\kindledesk-fb.raw"
(Get-Item "$env:TEMP\kindledesk-fb.raw").Length
```

## 决策顺序

### A. daemon 本机不可达

在主项目目录运行：

```bash
python -m pip install Pillow
python daemon/serve.py
```

看到 `starting KindleDesk card server on 0.0.0.0:8000` 后重新请求 `/fb`。

### B. KUAL 中没有 KindleDesk

让用户 USB 连接 Kindle，把主仓库 `kual-extensions/kindledesk/` 完整复制到：

```text
/mnt/us/extensions/kindledesk/
```

重新打开 KUAL，应该出现 `Start display (PULL)`、`Stop display` 与 `Setup & tools`。

### C. `fbink` 缺失

让用户安装 KOReader Kindle 包，并确认：

```text
/mnt/us/koreader/fbink
```

不要用不匹配型号的二进制替代。

### D. PC 地址未配置或错误

让用户通过 USB 创建 `/mnt/us/kindledesk/pc_ip`，内容为：

```text
http://<PC局域网IPv4>:8000
```

不能写 `127.0.0.1`，也不能写 Kindle 自己的 IP。KUAL 的 `Set / show PC IP` 用于显示当前值，屏幕菜单本身不能输入地址。

### E. daemon 正常，但 Kindle 没拉取

让用户执行：

```text
KUAL → KindleDesk → Start display (PULL)
```

等待最多 60 秒。检查两个证据：

1. daemon 终端出现 Kindle 发来的 `GET /fb`；
2. `/mnt/us/kindledesk/loop.log` 出现 `OK size=486400`。

如果 `curl` 失败，检查两台设备是否在同一可互访 LAN、Windows 防火墙是否仅在专用网络允许 Python、路由器是否开启客户端隔离。

### F. 拉取正常，屏幕仍不正确

- raw 大小不是设备预期值：立即停止循环，说明型号/framebuffer 不兼容。
- 方向或 stride 错误：不要继续直写，当前项目只验证过 Kindle Basic 3。
- 画面被系统界面覆盖：等待下一次 PULL；不要自动停止 Kindle framework。

### G. 全部就绪

告诉用户端到端链路已就绪，并询问是否推送一个测试 widget。只有用户明确同意后，才使用 `widget.py ... --push`。

## 完整人工步骤

所有复制命令、Windows 盘符示例和验收标准见：

[完整安装指南](../SETUP.md)
