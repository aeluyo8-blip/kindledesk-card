#!/bin/sh
# Restart Kindle framework to pick up new screensaver files.
# This causes a brief flash/black screen (~2-3 seconds).
# Only needed ONCE after the first screensaver file is placed.
#
# After restart, the framework will recognize kindledesk_ss.png as a valid screensaver.
# Subsequent updates to the same file do NOT need framework restart.
LOG=/mnt/us/kindledesk/restart_framework.log

echo "$(date) restarting framework..." >> "$LOG"

# Try the upstart way first (most reliable)
stop framework 2>/dev/null && start framework 2>/dev/null
RESULT=$?

if [ "$RESULT" -ne 0 ]; then
    # fallback: lipc command
    lipc-set-prop com.lab126.appmgrd appRestartNow 1 2>/dev/null
    RESULT=$?
fi

echo "$(date) framework restart exit=$RESULT" >> "$LOG"

if [ "$RESULT" -eq 0 ]; then
    echo "Framework restarted. Screen will flash briefly."
    echo "Your screensaver should now be active."
else
    echo "Framework restart may have failed (exit=$RESULT)."
    echo "Try manually: [HOME] > [MENU] > Settings > [MENU] > Restart"
fi
