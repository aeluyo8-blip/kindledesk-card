#!/bin/sh
# Stop push receiver — guaranteed exit from PUSH card mode.
# Kills the push_recv.sh process, restores touch driver, releases wakelock,
# frees the 9876 port, and re-enables screensaver. Use this if the power-key
# short-press exit isn't working on your firmware.
LOG=/mnt/us/kindledesk/push.log
log() { echo "$(date) $*" >> "$LOG"; }

log "=== stop_push requested ==="

# kill the receiver (and its power monitors)
pkill -f "push_recv.sh" 2>/dev/null
pkill -f "od -An" 2>/dev/null
pkill -f "lipc-wait-event" 2>/dev/null
pkill -x nc 2>/dev/null

# restore touch
modprobe cyttsp5_i2c 2>/dev/null
modprobe cyttsp5 2>/dev/null

# release wakelock + re-enable screensaver
echo kindledesk > /sys/power/wake_unlock 2>/dev/null
lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null

# free inbound port rule (best-effort)
iptables -D INPUT -p tcp --dport 9876 -j ACCEPT 2>/dev/null

/usr/sbin/eips "push stopped" 2>/dev/null
log "push receiver stopped, touch restored"
