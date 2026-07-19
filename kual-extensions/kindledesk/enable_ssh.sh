#!/bin/sh
# enable_ssh.sh — start dropbear over WiFi so the PC can ssh in (key-auth only).
# Before running, copy the PC public key to /mnt/us/ssh/authorized_keys.
LOG=/mnt/us/kindledesk/enable_ssh.log
export PATH=/usr/bin:/bin:/sbin:/usr/sbin:$PATH
{
echo "$(date) === enable_ssh ==="

# 1) locate dropbear
DB=""
for p in /usr/sbin/dropbear /sbin/dropbear /mnt/us/usbnet/bin/dropbear /opt/bin/dropbear; do
    [ -x "$p" ] && DB="$p" && break
done
echo "dropbear: ${DB:-NOT FOUND}"
[ -z "$DB" ] && { echo "FATAL: dropbear binary missing — cannot enable SSH"; exit 2; }

# 2) host keys (dropbear needs them; generate if absent)
HKDIR=/tmp
if [ ! -f "$HKDIR/dropbear_rsa_host_key" ] && command -v dropbearkey >/dev/null 2>&1; then
    dropbearkey -t rsa -f "$HKDIR/dropbear_rsa_host_key" 2>&1
fi
if [ ! -f "$HKDIR/dropbear_dss_host_key" ] && command -v dropbearkey >/dev/null 2>&1; then
    dropbearkey -t dss -f "$HKDIR/dropbear_dss_host_key" 2>&1
fi

# 3) install the user-provided PC public key (key-auth only, no password)
PUBKEY=/mnt/us/ssh/authorized_keys
[ -s "$PUBKEY" ] || {
    echo "FATAL: $PUBKEY is missing or empty"
    echo "Copy your PC public key there over USB, then retry."
    exit 3
}
mkdir -p /root/.ssh
cp "$PUBKEY" /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
echo "authorized_keys installed"

# 4) firewall: allow 22
iptables -I INPUT -p tcp --dport 22 -j ACCEPT 2>/dev/null
echo "iptables: 22 allowed"

# 5) start dropbear (WiFi, all interfaces). Skip if already running.
mkdir -p /mnt/us/ssh
if [ -f /mnt/us/ssh/dropbear.pid ] && kill -0 "$(cat /mnt/us/ssh/dropbear.pid 2>/dev/null)" 2>/dev/null; then
    echo "dropbear already running (pid $(cat /mnt/us/ssh/dropbear.pid)), skip start"
else
    $DB -p 22 -P /mnt/us/ssh/dropbear.pid 2>&1
fi
sleep 1
echo "--- port 22 listening? ---"
netstat -tln 2>/dev/null | grep :22 || ss -tln 2>/dev/null | grep :22 || echo "NOT LISTENING"
echo "--- dropbear proc ---"
ps 2>/dev/null | grep dropbear | grep -v grep
echo "done"
} > "$LOG" 2>&1
cat "$LOG"
