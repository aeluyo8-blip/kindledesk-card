#!/bin/sh
# KindleDesk boot autostart: runs once on Kindle boot, fixes screensaver
# (rootfs resets on reboot) and starts the PULL display loop.
# Installed by boot_install.sh as /etc/crontabs/root @reboot.

DIR=/mnt/us/kindledesk
EXT=/mnt/us/extensions/kindledesk
LOG=$DIR/autostart.log
SS_SRC=$DIR/linkss/screensavers/kindledesk_ss.png
SS_SYS=/usr/share/blanket/screensaver

log() { echo "$(date) $*" >> "$LOG"; }

mkdir -p "$DIR"
log "=== autostart pid=$$ ==="

# Wait for WiFi to come up. Most home networks take 15-40s after boot.
sleep 30

# Resolve PC URL (same logic as fetch_loop/start_display/push_recv).
PC="${KD_PC:-}"
[ -z "$PC" ] && [ -f "$DIR/pc_ip" ] && PC="$(cat "$DIR/pc_ip" 2>/dev/null | head -1 | tr -d '\r\n[:space:]')"
[ -z "$PC" ] && { log "PC URL missing; configure $DIR/pc_ip"; exit 2; }
log "PC resolved: $PC"

# If the screensaver source exists and the system copy differs, fix it.
# We compare file size of the first system file vs our source as a cheap check.
if [ -f "$SS_SRC" ]; then
    SYS_SIZE=$(wc -c < "$SS_SYS/bg_ss00.png" 2>/dev/null || echo 0)
    SRC_SIZE=$(wc -c < "$SS_SRC" 2>/dev/null || echo 0)
    if [ "$SYS_SIZE" -ne "$SRC_SIZE" ]; then
        log "screensaver mismatch sys=$SYS_SIZE src=$SRC_SIZE, running fix_screensaver"
        sh "$EXT/fix_screensaver.sh" >> "$LOG" 2>&1
    else
        log "screensaver already customized (sizes match)"
    fi
else
    log "screensaver source missing ($SS_SRC), skipping fix"
fi

# Start the display loop if not already running.
if [ -f "$DIR/loop.pid" ] && kill -0 "$(cat "$DIR/loop.pid" 2>/dev/null)" 2>/dev/null; then
    log "loop already running"
else
    log "starting loop"
    sh "$EXT/start_loop.sh" >> "$LOG" 2>&1
fi

# SSH is opt-in. Create /mnt/us/kindledesk/enable_ssh_on_boot only after
# installing /mnt/us/ssh/authorized_keys and accepting the LAN exposure.
if [ -f "$DIR/enable_ssh_on_boot" ]; then
    log "SSH boot marker found; ensuring dropbear is up"
    sh "$EXT/enable_ssh.sh" >> "$LOG" 2>&1
else
    log "SSH boot marker absent; skipping SSH"
fi

log "=== autostart done ==="
