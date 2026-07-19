# KindleDesk 运行期连接检查

仅在 daemon 不可达、推送失败或 Kindle 长时间没有更新时读取。设备越狱、KUAL、KOReader 和扩展部署属于一次性安装，交给仓库根目录的 `SETUP.md`，不要在本 Skill 中重复执行。

## 连接模型

```text
widget.py → POST PC daemon :8000 → widget cache
                                      ↑
Kindle fetch_loop ← GET /fb every 60s ┘
```

默认是 PULL：Skill 只访问 PC 本机 daemon，不直接登录或控制 Kindle。

## 1. 检查 daemon

先请求当前状态：

```bash
curl -f "${KINDLEDESK_URL:-http://127.0.0.1:8000}/widgets"
```

不可达时，报告 daemon 未运行或地址错误。若已知项目目录，可提示用户运行：

```bash
python daemon/serve.py
```

不要重新安装 Kindle 端组件，也不要自动重启 Kindle。

## 2. 检查 PULL 地址

Kindle 的 `/mnt/us/kindledesk/pc_ip` 必须是：

```text
http://<PC局域网IPv4>:8000
```

不能填 `127.0.0.1`，也不能填 Kindle 自己的 IP。用户可通过 USB 修改该文件，再用 KUAL → KindleDesk → Setup & tools → Set / show PC IP 检查当前值。

## 3. 判断 Kindle 是否仍在拉取

成功推送 widget 但 60 秒后屏幕未更新时，让用户检查：

- daemon 终端是否出现 Kindle 发来的 `GET /fb`；
- `/mnt/us/kindledesk/loop.log` 是否出现 `OK size=486400`；
- Kindle 与 PC 是否位于同一可互访 LAN；
- Windows 防火墙是否允许 Python 通过专用网络接收连接。

没有 `GET /fb` 时，问题位于 Kindle → PC 的 PULL 链路，不要重复 POST widget。

## 4. 即时 PUSH（仅用户明确启用时）

即时 PUSH 需要 Kindle 运行 `Start push (instant card)`，并在 PC daemon 环境中设置：

```text
KINDLEDESK_KINDLE_IP=<Kindle局域网IPv4>
```

普通 PULL 不需要该变量。不要自动切换到 PUSH、SSH 或 USB。

## 安全边界

- 不执行越狱、MRPI/KUAL/KOReader 安装或扩展复制。
- 不修改 Kindle 系统文件、屏保或开机项。
- 不自动打开防火墙、切换网络、启用 SSH或重启设备。
- 连接仍失败时，给出已确认的 daemon、PC IP 和日志状态，让用户决定下一步。
