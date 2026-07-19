#!/bin/sh
# Remove the KindleDesk @reboot autostart entry from /etc/crontabs/root.
# Does NOT delete the backup made by boot_install.sh.

DIR=/mnt/us/kindledesk
EXT=/mnt/us/extensions/kindledesk
CRON=/etc/crontabs/root

if [ -f "$CRON" ]; then
    grep -vF "$EXT/autostart.sh" "$CRON" > "$CRON.tmp" && mv "$CRON.tmp" "$CRON" || true
fi

echo "KindleDesk boot autostart removed."
