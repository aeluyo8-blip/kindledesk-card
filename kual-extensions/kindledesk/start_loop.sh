#!/bin/sh
# Launch the display loop detached from KUAL.
# Kindle busybox may lack nohup, so try setsid -> nohup -> plain &.
DIR=/mnt/us/kindledesk           # data dir (pid/log/png)
EXTDIR=/mnt/us/extensions/kindledesk  # script dir (where this file lives)
LOOP=$EXTDIR/fetch_loop.sh
PID=$DIR/loop.pid
LOG=$DIR/loop.log
FBINK=/mnt/us/koreader/fbink

mkdir -p "$DIR"

{
echo "=== $(date) start_loop ==="

# already running?
if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    echo "already running pid $(cat "$PID")"
    "$FBINK" "loop running pid $(cat "$PID")"
    exit 0
fi

# pick a detach method (Kindle busybox may lack nohup/setsid)
if command -v setsid >/dev/null 2>&1; then
    DM=setsid
    setsid sh "$LOOP" >> "$LOG" 2>&1 < /dev/null &
elif command -v nohup >/dev/null 2>&1; then
    DM=nohup
    nohup sh "$LOOP" >> "$LOG" 2>&1 < /dev/null &
else
    DM=amp
    sh "$LOOP" >> "$LOG" 2>&1 < /dev/null &
fi
BGPID=$!
echo "detach=$DM pid=$BGPID"
echo "$BGPID" > "$PID"

sleep 3
if kill -0 "$BGPID" 2>/dev/null; then
    echo "ALIVE ok"
    "$FBINK" "loop started pid $BGPID"
else
    echo "DEAD after 3s"
    sh -n "$LOOP" 2>&1 && echo "fetch_loop syntax OK" || echo "fetch_loop SYNTAX ERR"
    "$FBINK" "loop FAIL dm=$DM see log"
fi
} >> "$LOG" 2>&1
