#!/bin/sh
# Display loop body (runs detached). Pull raw framebuffer bytes from PC every
# INTERVAL sec, write directly to /dev/fb0, refresh eink. Bypasses fbink -i
# (KOReader fbink has no image decoder) and eips (unreliable).
#
# PC serves /fb = 486400 bytes (800 rows x 608 stride; 600 px + 8 pad) matching
# Kindle Basic 3 /dev/fb0 layout.
# PC base URL. Resolution order:
#   1. env KD_PC            (e.g. http://192.168.31.10:8000)
#   2. file /mnt/us/kindledesk/pc_ip
# Missing configuration is fatal; set /mnt/us/kindledesk/pc_ip first.
PC="${KD_PC:-}"
[ -z "$PC" ] && [ -f /mnt/us/kindledesk/pc_ip ] && PC="$(cat /mnt/us/kindledesk/pc_ip 2>/dev/null | head -1 | tr -d '\r\n[:space:]')"
[ -z "$PC" ] && { echo "PC URL missing: configure /mnt/us/kindledesk/pc_ip" >> /mnt/us/kindledesk/loop.log; exit 2; }
FB=/fb
SS=/screensaver
OUT=/tmp/fb.raw
SS_OUT=/tmp/kindledesk_ss.png
SS_DIR=/mnt/us/linkss/screensavers
SS_FILE=${SS_DIR}/kindledesk_ss.png
FBINK=/mnt/us/koreader/fbink
INTERVAL=60
SS_EVERY=5  # sync screensaver every N cycles (5 = every 5 min)
LOG=/mnt/us/kindledesk/loop.log

log() { echo "$(date) $*" >> "$LOG"; }

# --- prevent Kindle sleep (defense in depth) ---
# 1. kernel wakelock: holds the system awake so powerd can't freeze this proc.
echo kindledesk > /sys/power/wake_lock 2>/dev/null && log "wakelock acquired" || log "wakelock N/A (/sys/power/wake_lock absent — will rely on powerd)"

# 2. powerd auto-suspend: large period (0 is sometimes ignored/reset).
poke_sleep() {
    lipc-set-prop -i com.lab126.powerd powerdSuspendPeriod 99999 2>/dev/null
}
poke_sleep

# release wakelock when the loop dies so a stopped loop doesn't hold awake forever
trap 'echo kindledesk > /sys/power/wake_unlock 2>/dev/null; log "loop exit pid=$$, wakelock released"' EXIT INT TERM

log "=== loop start pid=$$ interval=${INTERVAL}s fb-direct ==="

CYCLE=0

mkdir -p "$SS_DIR" 2>/dev/null

while true; do
    poke_sleep   # re-poke each cycle in case powerd reset the period
    CYCLE=$((CYCLE + 1))

    # --- framebuffer update (every cycle) ---
    curl -s -m 20 -o "$OUT" "$PC$FB"
    CEXIT=$?
    SIZE=$([ -f "$OUT" ] && wc -c < "$OUT" || echo 0)
    if [ "$CEXIT" = 0 ] && [ "$SIZE" -gt 100000 ]; then
        cat "$OUT" > /dev/fb0 2>/dev/null
        WEXIT=$?
        "$FBINK" -s -W GC16 >/dev/null 2>&1
        REXIT=$?
        log "OK size=$SIZE fbwrite=$WEXIT refresh=$REXIT"
    else
        log "FAIL curl=$CEXIT size=$SIZE"
    fi

    # --- screensaver sync (every SS_EVERY cycles) ---
    if [ $((CYCLE % SS_EVERY)) -eq 0 ]; then
        curl -s -m 20 -o "$SS_OUT" "$PC$SS" 2>/dev/null
        SS_SIZE=$([ -f "$SS_OUT" ] && wc -c < "$SS_OUT" || echo 0)
        if [ "$SS_SIZE" -gt 1000 ]; then
            if cp "$SS_OUT" "$SS_FILE" 2>/dev/null; then
                # verify the copy
                WRITTEN=$(wc -c < "$SS_FILE" 2>/dev/null || echo 0)
                log "SS synced size=$SS_SIZE written=$WRITTEN"
            else
                log "SS FAIL cp failed"
            fi
        else
            log "SS FAIL size=$SS_SIZE"
        fi
    fi

    sleep "$INTERVAL"
done
