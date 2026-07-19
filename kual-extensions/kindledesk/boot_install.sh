#!/bin/sh
# Install KindleDesk boot autostart via @reboot crontab entry.
# Safe and reversible: backs up /etc/crontabs/root before editing.
set -e

DIR=/mnt/us/kindledesk
EXT=/mnt/us/extensions/kindledesk
CRON=/etc/crontabs/root
BACKUP=$DIR/backup/crontabs_root

mkdir -p "$DIR/backup"

# Backup current crontab if present and not already backed up
if [ ! -f "$BACKUP" ] && [ -f "$CRON" ]; then
    cp "$CRON" "$BACKUP"
    echo "backed up $CRON -> $BACKUP"
fi

# Remove any existing KindleDesk autostart line to avoid duplicates
if [ -f "$CRON" ]; then
    grep -vF "$EXT/autostart.sh" "$CRON" > "$CRON.tmp" || cp "$CRON" "$CRON.tmp"
else
    : > "$CRON.tmp"
fi

# Add the @reboot entry
echo "@reboot $EXT/autostart.sh >> $DIR/autostart.log 2>&1" >> "$CRON.tmp"
mv "$CRON.tmp" "$CRON"

# Signal crond to re-read if it is running
if pidof crond >/dev/null 2>&1; then
    kill -HUP $(pidof crond) 2>/dev/null || true
fi

echo "KindleDesk boot autostart installed."
