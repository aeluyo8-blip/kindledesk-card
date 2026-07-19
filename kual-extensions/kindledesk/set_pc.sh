#!/bin/sh
# Set the PC URL for KindleDesk. Run on device via SSH, or create the file
# from PC over USB: echo 'http://192.168.31.10:8000' > /mnt/us/kindledesk/pc_ip
#
# Usage examples:
#   set_pc.sh http://192.168.31.10:8000
#   set_pc.sh 192.168.31.10
#   set_pc.sh 192.168.31.10:8000

set -e

CONF=/mnt/us/kindledesk/pc_ip
FBINK=/mnt/us/koreader/fbink

show() { "$FBINK" "$*" 2>/dev/null || true; }

if [ $# -eq 0 ]; then
    # no args: display current configuration
    if [ -f "$CONF" ]; then
        echo "current PC: $(cat "$CONF" 2>/dev/null | head -1 | tr -d '\r\n')"
    else
        echo "current PC: (not set)"
    fi
    show "edit $CONF on PC" 2>/dev/null
    exit 0
fi

url="$1"

# normalize: add http:// if missing, add :8000 if no port
fix() {
    case "$1" in
        http://*|https://*) echo "$1" ;;
        *:*) echo "http://$1" ;;
        *) echo "http://$1:8000" ;;
    esac
}
url=$(fix "$url")

mkdir -p "$(dirname "$CONF")"
printf '%s\n' "$url" > "$CONF"
sync

show "PC=$url"
echo "PC=$url"
