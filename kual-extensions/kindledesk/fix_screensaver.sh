#!/bin/sh
# Fix screensaver: copy our image to replace ALL default screensavers.
# Instead of bind mount (which broke the framework), we replace each
# default screensaver file with our custom image.
# Framework expects files named bg_ss*.png — we keep the names, replace content.

SS_SRC=/mnt/us/linkss/screensavers/kindledesk_ss.png
SYS_SS=/usr/share/blanket/screensaver
LOG=/mnt/us/kindledesk/fix_ss.log
EIPS=/usr/sbin/eips

disp() { $EIPS 2 "$2" "$1" 2>/dev/null; echo "$1" >> "$LOG"; }

echo "$(date) === fix_screensaver (copy mode) ===" > "$LOG"

$EIPS -c 2>/dev/null

# 1. remount rootfs rw
mount -o remount,rw / 2>>"$LOG"
disp "rootfs: rw" 0

# 2. check source
if [ ! -f "$SS_SRC" ]; then
    disp "ERROR: $SS_SRC not found!" 1
    mount -o remount,ro / 2>/dev/null
    exit 1
fi
SS_SIZE=$(wc -c < "$SS_SRC" 2>/dev/null)
disp "source: $SS_SIZE bytes" 1

# 3. backup originals (first time only)
if [ ! -d /mnt/us/linkss/screensavers/backup_original ]; then
    mkdir -p /mnt/us/linkss/screensavers/backup_original
    cp "$SYS_SS"/*.png /mnt/us/linkss/screensavers/backup_original/ 2>>"$LOG"
    cp "$SYS_SS"/*.jpg /mnt/us/linkss/screensavers/backup_original/ 2>>"$LOG"
    disp "backup: saved originals" 2
else
    disp "backup: already exists" 2
fi

# 4. replace every screensaver file with our image
COUNT=0
for f in "$SYS_SS"/*; do
    if [ -f "$f" ]; then
        cp "$SS_SRC" "$f" 2>>"$LOG"
        COUNT=$((COUNT + 1))
    fi
done
disp "replaced $COUNT files" 3

# 5. verify one file
if [ -f "$SYS_SS/bg_ss00.png" ]; then
    VSIZE=$(wc -c < "$SYS_SS/bg_ss00.png")
    disp "verify bg_ss00: $VSIZE bytes" 4
fi

# 6. remount ro
mount -o remount,ro / 2>>"$LOG"
disp "rootfs: ro" 5

disp "" 6
disp "Done! Press power to sleep." 7
echo "$(date) === done ===" >> "$LOG"
