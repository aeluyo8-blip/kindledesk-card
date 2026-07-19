#!/bin/sh
# PUSH receiver — listen on PORT, receive PNG, display via eips -f -g.
# PC/agent pushes PNG → Kindle shows it. Framework stays ALIVE (no stop, no
# framebuffer direct write, no reboot to recover). In-mode exit = SHORT
# POWER-KEY PRESS, detected via lipc (preventScreenSaver stays on so a stray
# touch can't exit — XInput temporarily disables touch to avoid accidents).
PORT=9876

# PC base URL (initial draw). Resolution: KD_PC env > /mnt/us/kindledesk/pc_ip.
PC="${KD_PC:-}"
[ -z "$PC" ] && [ -f /mnt/us/kindledesk/pc_ip ] && PC="$(cat /mnt/us/kindledesk/pc_ip 2>/dev/null | head -1 | tr -d '\r\n[:space:]')"
[ -z "$PC" ] && { echo "PC URL missing: configure /mnt/us/kindledesk/pc_ip" >> /mnt/us/kindledesk/push.log; exit 2; }

LOG=/mnt/us/kindledesk/push.log
IMG=/tmp/push.png
EIPS=/usr/sbin/eips
LUAJIT=/mnt/us/koreader/luajit
TOUCH_TOGGLE="$(dirname "$0")/touch_toggle.lua"
TOUCH_DISABLED=0

log() { echo "$(date) $*" >> "$LOG"; }

# prevent sleep (no polling loop, so we hold awake ourselves)
echo kindledesk > /sys/power/wake_lock 2>/dev/null && log "wakelock acquired" || log "wakelock N/A"
lipc-set-prop -i com.lab126.powerd powerdSuspendPeriod 99999 2>/dev/null

# open iptables for inbound push
iptables -I INPUT 1 -p tcp --dport $PORT -j ACCEPT 2>/dev/null
log "iptables opened :$PORT"

# Disable touch inside Xorg without removing the kernel input device. Xorg and
# deviced keep their live file descriptors, so enabling it later is immediate.
if [ -x "$LUAJIT" ] && [ -f "$TOUCH_TOGGLE" ] && "$LUAJIT" "$TOUCH_TOGGLE" 0 >> "$LOG" 2>&1; then
    TOUCH_DISABLED=1
    log "touch disabled (XInput)"
else
    log "touch disable unavailable; leaving touch enabled"
fi

# Short power-key press: framework stays alive (we no longer chmod event
# nodes — that crashed it and caused spurious reboots). Lock/screensaver is
# prevented via powerd lipc below. Long-press 7s = PMIC reboot (exit path).
lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null && log "screensaver prevented (short power press safe)"

EXIT_REASON=signal
MONITOR_PIDS=""
NC_PID=""
cleanup() {
    [ -n "$NC_PID" ] && kill "$NC_PID" 2>/dev/null
    for pid in $MONITOR_PIDS; do kill "$pid" 2>/dev/null; done
    if [ "$TOUCH_DISABLED" = 1 ]; then
        "$LUAJIT" "$TOUCH_TOGGLE" 1 >> "$LOG" 2>&1
        TOUCH_RC=$?
    else
        TOUCH_RC=0
    fi
    echo kindledesk > /sys/power/wake_unlock 2>/dev/null
    lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null
    iptables -D INPUT -p tcp --dport $PORT -j ACCEPT 2>/dev/null
    [ -e /dev/input/event2 ] && TOUCH_EVENT=present || TOUCH_EVENT=missing
    log "exit pid=$$ reason=$EXIT_REASON, touch_rc=$TOUCH_RC event2=$TOUCH_EVENT"
}
trap cleanup EXIT
trap 'exit 0' INT TERM
trap 'EXIT_REASON=power; exit 0' USR1

log "=== push receiver pid=$$ :$PORT (eips -f -g, framework alive) ==="
"$EIPS" "push :$PORT" 2>/dev/null

# initial draw so screen isn't blank before first push
curl -s -m 20 -o "$IMG" "$PC/card.png" 2>/dev/null
if [ "$(wc -c < "$IMG" 2>/dev/null || echo 0)" -gt 1000 ]; then
    "$EIPS" -f -g "$IMG" >/dev/null 2>&1
    log "init draw OK"
fi
# on-screen exit hint: short power-key press → back to KUAL
"$EIPS" 20 590 "短按电源键 退出" 2>/dev/null

# Graceful exit on short power-key press.
# The framework grabs the power-key evdev node, so reading /dev/input/event*
# usually sees nothing. The hardware abstraction layer broadcasts the button
# as com.lab126.hal/powerButtonPressed; this stays observable despite the grab.
# Keep the older powerd event and raw evdev readers as firmware fallbacks.
MAINPID=$$
power_mon_hal() {
    command -v lipc-wait-event >/dev/null 2>&1 || return 0
    lipc-wait-event com.lab126.hal powerButtonPressed >/dev/null 2>&1
    log "power key (hal) → exit"
    kill -USR1 "$MAINPID" 2>/dev/null
}
power_mon_hal &
MONITOR_PIDS="$MONITOR_PIDS $!"

power_mon_powerd() {
    command -v lipc-wait-event >/dev/null 2>&1 || return 0
    lipc-wait-event com.lab126.powerd goingToScreenSaver >/dev/null 2>&1
    log "power key (powerd fallback) → exit"
    kill -USR1 "$MAINPID" 2>/dev/null
}
power_mon_powerd &
MONITOR_PIDS="$MONITOR_PIDS $!"

power_mon_od() {
    local dev="$1"
    od -An -v -tx1 "$dev" 2>/dev/null | \
        grep -m1 -E '00 01 00 74 00 00 00 0[1-9a-fA-F]' >/dev/null 2>&1
    log "power key ($dev) → exit"; kill -USR1 "$MAINPID" 2>/dev/null
}
log "power-exit monitor: hal (primary) + powerd/od fallback"
for d in /dev/input/event*; do
    if [ -c "$d" ]; then
        power_mon_od "$d" &
        MONITOR_PIDS="$MONITOR_PIDS $!"
    fi
done

# listen loop: nc -l accepts one connection, receives PNG, exits, we loop
while true; do
    lipc-set-prop -i com.lab126.powerd powerdSuspendPeriod 99999 2>/dev/null
    nc -l -p $PORT > "$IMG" 2>>"$LOG" &
    NC_PID=$!
    wait "$NC_PID"
    NC_PID=""
    SIZE=$(wc -c < "$IMG" 2>/dev/null || echo 0)
    if [ "$SIZE" -gt 1000 ]; then
        "$EIPS" -f -g "$IMG" >/dev/null 2>&1
        log "PUSH OK size=$SIZE"
    else
        log "recv size=$SIZE (ignored)"
    fi
done
