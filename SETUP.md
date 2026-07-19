# KindleDesk 完整安装指南

目标：把一台已越狱 Kindle 配置到能够从 PC 拉取 KindleDesk 画面。首次配置约 15–30 分钟，不包含越狱本身所需时间。

> 当前已验证设备是 Kindle Basic 3（600×800）。其他型号先确认屏幕分辨率和 framebuffer 布局，不要直接运行显示循环。

## 0. 先确认型号、固件和越狱状态

在 Kindle 打开 **设置 → 设备选项 → 设备信息**，记录型号和固件版本。越狱方式会随型号、固件版本变化，不要照搬其他型号的文件。

- 越狱入口：[MobileRead Kindle Developer's Corner](https://www.mobileread.com/forums/forumdisplay.php?f=150)
- KUAL 上游讨论：[KUAL: Kindle Unified Application Launcher](https://www.mobileread.com/forums/showthread.php?t=203326)
- MRPI 上游讨论：[MobileRead Package Installer](https://www.mobileread.com/forums/showthread.php?t=251143)

严格按与你的型号和固件匹配的越狱指南执行，并安装对应的 hotfix。完成后再继续本页。不要在不确定兼容性时安装 `.bin` 包或升级固件。

完成标准：Kindle 已越狱，重启后越狱仍然有效。

## 1. 安装 MRPI 和 KUAL

下载适用于当前固件的 MRPI 与 KUAL 包，并以各自上游说明为准。常见安装过程如下：

1. USB 连接 Kindle。
2. 把 MRPI 压缩包解压到 Kindle USB 根目录。完成后应存在 `mrpackages/` 和 MRPI 扩展目录。
3. 把 KUAL 的安装 `.bin` 放进 Kindle 的 `mrpackages/`。
4. 安全弹出 Kindle。
5. 在 Kindle 搜索框输入 `;log mrpi` 并确认，等待安装完成。
6. 在书库中打开 KUAL。

不同固件可能使用 KUAL Booklet 或 Coplate，文件名和安装顺序可能不同；如果上游说明与以上概览冲突，以上游说明为准。

完成标准：KUAL 能正常打开并显示扩展菜单。

## 2. 安装 KOReader，取得 fbink

KindleDesk 用 KOReader 随附的 `fbink` 刷新墨水屏。

1. 从 [KOReader Releases](https://github.com/koreader/koreader/releases) 下载 Kindle 安装包。
2. USB 连接 Kindle，把压缩包内容按 KOReader 的 Kindle 安装说明复制到 USB 根目录。
3. 确认 Kindle 盘符中存在 `koreader/fbink`。
4. 安全弹出后重新打开 KUAL，确认 KOReader 菜单存在。

完成标准：Kindle 内部路径 `/mnt/us/koreader/fbink` 存在且可执行。

## 3. 在 PC 安装 KindleDesk

需要 Python 3 和 Git。Windows PowerShell：

```powershell
git clone https://github.com/aeluyo8-blip/kindledesk-card.git
cd kindledesk-card
python -m pip install Pillow
python tests/test_push_templates.py -v
```

测试全部通过后再部署 Kindle 端脚本。

## 4. 部署 KUAL 扩展

USB 连接 Kindle。假设 Kindle 盘符是 `E:`，在项目根目录执行：

```powershell
New-Item -ItemType Directory -Force E:\extensions\kindledesk | Out-Null
Copy-Item -Recurse -Force .\kual-extensions\kindledesk\* E:\extensions\kindledesk\
```

对应关系：

```text
PC 仓库 kual-extensions/kindledesk/
    ↓
Kindle USB E:\extensions\kindledesk\
    ↓
Kindle 内部 /mnt/us/extensions/kindledesk/
```

本仓库用 `.gitattributes` 保证 shell 脚本为 LF。若你通过其他方式编辑过 `.sh` 文件，必须确认没有 CRLF，否则 Kindle 的 `/bin/sh` 会报错。

安全弹出 Kindle，关闭并重新打开 KUAL。此时应看到 **KindleDesk** 菜单。

完成标准：KUAL 中出现 `Start display (PULL)`、`Stop display` 和 `Setup & tools`。

## 5. 配置 PC 局域网地址

Kindle 主动访问 PC，所以这里写的是 **PC 的局域网 IPv4**，不是 Kindle IP，也不是 `127.0.0.1`。

在 PC 运行：

```powershell
ipconfig
```

找到当前 Wi-Fi 网卡的 IPv4，例如 `192.168.31.10`。再次 USB 连接 Kindle并执行：

```powershell
New-Item -ItemType Directory -Force E:\kindledesk | Out-Null
Set-Content -LiteralPath E:\kindledesk\pc_ip -Value 'http://192.168.31.10:8000' -NoNewline
```

把示例地址替换为你的真实地址。对应的 Kindle 内部文件是：

```text
/mnt/us/kindledesk/pc_ip
```

安全弹出后，在 KUAL 打开 **KindleDesk → Setup & tools → Set / show PC IP**。菜单会显示当前配置；地址修改仍需通过上述文件或 SSH 命令完成。

完成标准：显示的地址为 `http://<PC局域网IPv4>:8000`。

## 6. 启动 PC daemon

在项目根目录运行：

```powershell
python daemon/serve.py
```

首次启动会获取天气数据，可能等待约 10 秒。看到以下信息即启动成功：

```text
starting KindleDesk card server on 0.0.0.0:8000
```

保持此窗口运行。另开一个 PowerShell 验证：

```powershell
curl.exe -f http://127.0.0.1:8000/card.png -o "$env:TEMP\kindledesk-card.png"
curl.exe -f http://127.0.0.1:8000/fb -o "$env:TEMP\kindledesk-fb.raw"
(Get-Item "$env:TEMP\kindledesk-fb.raw").Length
```

预期结果：两个请求成功，raw 文件大小为 `486400` 字节。

如果 Windows 防火墙询问是否允许 Python 接收连接，只允许可信的“专用网络”。

## 7. 从 Kindle 验证网络

确保 Kindle 与 PC 连接同一个可信 Wi-Fi，且客户端隔离未开启。然后在 Kindle 打开：

```text
KUAL → KindleDesk → Start display (PULL)
```

等待最多 60 秒。正常时：

- Kindle 显示 KindleDesk 卡片；
- PC daemon 终端出现来自 Kindle IP 的 `GET /fb`；
- Kindle USB 数据目录 `/mnt/us/kindledesk/loop.log` 出现 `OK size=486400`。

完成标准：连续两次拉取均成功，且屏幕方向和内容正常。

## 8. 推送一个测试 widget

先安装 [kindledesk-card Skill](https://github.com/aeluyo8-blip/kindledesk-card)，或直接调用 daemon：

```powershell
$body = @{
  type = 'focus'
  slot = 'middle'
  data = @{ task = 'KindleDesk 配置完成'; subtitle = '端到端链路正常' }
} | ConvertTo-Json -Depth 4

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/widget `
  -ContentType 'application/json; charset=utf-8' `
  -Body $body
```

Kindle 会在下一次拉取（最多 60 秒）后更新。

完成标准：屏幕中间出现“KindleDesk 配置完成”。

## 9. 可选功能

### 开机自启

KUAL → **KindleDesk → Setup & tools → Enable boot autostart**。

此操作会备份并修改 `/etc/crontabs/root`，加入 KindleDesk 的 `@reboot` 任务。先完成手动启动和端到端验证，再考虑启用。卸载脚本保存在扩展目录的 `boot_uninstall.sh`。

### 自定义系统屏保

先让显示循环成功同步 `/mnt/us/linkss/screensavers/kindledesk_ss.png`，再运行 KUAL → **Setup & tools → Fix screensaver**。

该脚本会：

1. 临时把根文件系统重新挂载为可写；
2. 备份原屏保到 `/mnt/us/linkss/screensavers/backup_original/`；
3. 替换 `/usr/share/blanket/screensaver/` 中的系统屏保；
4. 把根文件系统重新挂载为只读。

这不是主显示链路的必要步骤。不要在未确认设备路径兼容时执行。

### SSH 排障

主线 PULL 不依赖 SSH。只有确实需要远程排障时才配置 dropbear 和密钥认证；不要启用密码登录，也不要把私钥提交到仓库。

## 故障定位

| 现象 | 检查 |
|---|---|
| KUAL 没有 KindleDesk | 确认目录是 `/mnt/us/extensions/kindledesk/`，并重新打开 KUAL |
| `fbink` 不存在 | 重新安装正确的 KOReader Kindle 包，检查 `/mnt/us/koreader/fbink` |
| PC 本机 curl 失败 | daemon 未启动、Pillow 未安装或 8000 端口被占用 |
| PC 本机成功，Kindle 拉取失败 | `pc_ip` 写错、两台设备不在同一 LAN、防火墙阻止 Python、路由器开启客户端隔离 |
| `loop.log` 报 `curl` 失败 | 先在 PC 确认局域网 IPv4，再重写 `/mnt/us/kindledesk/pc_ip` |
| `/fb` 大小不是 486400 | 当前 daemon/设备画布配置不匹配，停止显示循环，不要继续直写 framebuffer |
| 画面出现后又被覆盖 | Kindle framework 重绘了屏幕；等待下一次拉取，不要擅自停掉系统 framework |
| 中文显示方框 | PC 缺少 daemon 可用的中文字体；检查 Pillow 字体回退配置 |

停止显示循环：

```text
KUAL → KindleDesk → Stop display
```

如果显示脚本异常，先停止循环，再通过 USB 读取 `kindledesk/loop.log`。不要反复重启或修改 Kindle 系统文件。
