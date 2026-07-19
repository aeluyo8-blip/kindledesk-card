#!/bin/sh
# Launch PUSH receiver, detached. PID = sh process (so stop can kill it directly).
# Recover via reboot, or kill the pid (trap restores framework + touch).
SCRIPT=/mnt/us/extensions/kindledesk/push_recv.sh
LOG=/mnt/us/kindledesk/push.log
PIDFILE=/mnt/us/kindledesk/push.pid

echo "$(date) === start_push launch ===" >> "$LOG"
sh -n "$SCRIPT" 2>>"$LOG" || { echo "$(date) syntax error, abort" >> "$LOG"; exit 1; }

# nohup sh & — PID is the sh process itself, stop_loop kills it cleanly
nohup sh "$SCRIPT" >> "$LOG" 2>&1 < /dev/null &
PID=$!
echo "$PID" > "$PIDFILE"
sleep 2
if kill -0 "$PID" 2>/dev/null; then
    echo "$(date) push receiver launched pid=$PID" >> "$LOG"
    echo "OK pid=$PID"
else
    echo "$(date) push receiver FAILED to launch" >> "$LOG"
    echo "FAIL"
fi
