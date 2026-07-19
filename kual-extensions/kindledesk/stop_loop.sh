#!/bin/sh
# Stop ALL display processes + clean residue. Kill pidfile + process group
# (setsid children), broad ps grep, killall nc/eips/fbink. Restore framework + touch.
DIR=/mnt/us/kindledesk
FBINK=/mnt/us/koreader/fbink
export PATH=/usr/bin:/bin:/sbin:$PATH
LOG="$DIR/stop.log"

echo "$(date) === stop_all start ===" >> "$LOG"
echo "--- ps before ---" >> "$LOG"
ps 2>/dev/null >> "$LOG" 2>&1

# 1. kill pidfiles (SIGKILL + whole process group, in case setsid spawned children)
for p in loop display push; do
    if [ -f "$DIR/$p.pid" ]; then
        PID=$(cat "$DIR/$p.pid" 2>/dev/null)
        if [ -n "$PID" ]; then
            kill -9 "$PID" 2>/dev/null
            kill -9 -"$PID" 2>/dev/null   # kill process group (setsid)
            echo "killed $p pid=$PID +group" >> "$LOG"
        fi
        rm -f "$DIR/$p.pid"
    fi
done

# 2. broad ps grep — kill anything matching our scripts
for pat in push_recv fetch_loop start_display start_stable start_push; do
    for pid in $(ps 2>/dev/null | grep "$pat" | grep -v grep | awk '{print $1}'); do
        kill -9 "$pid" 2>/dev/null
        echo "killed -9 $pat pid=$pid" >> "$LOG"
    done
done

# 3. kill ALL nc listeners (free port 9876) — repeated in case of respawns
for pass in 1 2 3; do
    for pid in $(ps 2>/dev/null | grep "nc" | grep -v grep | awk '{print $1}'); do
        kill -9 "$pid" 2>/dev/null
        echo "killed -9 nc pid=$pid (pass $pass)" >> "$LOG"
    done
    sleep 0.5
done

# 4. kill leftover eips/fbink
for pid in $(ps 2>/dev/null | grep -E "eips|fbink" | grep -v grep | awk '{print $1}'); do
    kill -9 "$pid" 2>/dev/null
done

# 5. restore framework + touch driver (in case start_display/rmmod touched them)
/etc/init.d/framework start 2>/dev/null
modprobe cyttsp5_i2c 2>/dev/null
modprobe cyttsp5 2>/dev/null
echo "framework + touch restored" >> "$LOG"

echo "--- ps after ---" >> "$LOG"
ps 2>/dev/null >> "$LOG" 2>&1

sleep 1
"$FBINK" "stopped all" 2>/dev/null
echo "$(date) === stop_all done ===" >> "$LOG"
