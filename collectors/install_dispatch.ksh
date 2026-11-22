#!/usr/bin/ksh93
# install_dispatch.ksh  v0.2 - set up aix-mcp live collection on one AIX LPAR or VIOS.
# Part of aix-mcp (https://github.com/vyasdx/aix-mcp). Apache-2.0. Not affiliated with IBM.
#
# Run as root from the directory that holds dispatch and aix_storage_paths.ksh:
#   ksh93 install_dispatch.ksh -k aixmcp.pub -f "10.1.2.3,10.1.2.4" [-u aixmcp]
#   ksh93 install_dispatch.ksh -r [-u aixmcp]        # remove everything it created
#
# What it does (and nothing else):
#   1. creates a non-root user (default aixmcp) with no password: key login only
#   2. installs /opt/aixmcp/bin/dispatch and /opt/aixmcp/libexec/aix_storage_paths.ksh (root-owned)
#   3. creates /var/aixmcp/storage (root, 0700) for collector output kept on the host
#   4. writes ONE authorized_keys line: command="/opt/aixmcp/bin/dispatch",restrict,from="<-f list>"
#   5. adds ONE sudo rule: that user may run the collector as root with two exact argument
#      lists, nothing else (sudoers file is checked with visudo before it is put in place)
# Performance history needs no root: /var/perf/daily and topasout are readable by any user.

PATH=/usr/bin:/usr/sbin:/etc:/opt/freeware/bin:/opt/freeware/sbin
U=aixmcp; KEY=""; FROM=""; REMOVE=0
while getopts "u:k:f:r" o; do
    case $o in u) U=$OPTARG ;; k) KEY=$OPTARG ;; f) FROM=$OPTARG ;; r) REMOVE=1 ;; *) sed -n '2,20p' "$0"; exit 1 ;; esac
done
(( $(id -u) == 0 )) || { print "run as root"; exit 1; }
[[ $U == +([a-z0-9_]) ]] || { print "bad user name"; exit 1; }

BASE=/opt/aixmcp
STORE=/var/aixmcp/storage
COLL=$BASE/libexec/aix_storage_paths.ksh
# ask sudo where its policy lives (AIX Toolbox sudo uses /etc/sudoers and /etc/sudoers.d)
SUDOERS=$(sudo -V 2>/dev/null | sed -n 's/^Sudoers path: //p'); SUDOERS=${SUDOERS:-/etc/sudoers}
SUDOERS_D=$(dirname "$SUDOERS")/sudoers.d
RULE=$SUDOERS_D/aixmcp

if (( REMOVE )); then
    rm -f "$RULE"
    lsuser "$U" >/dev/null 2>&1 && rmuser -p "$U" && rm -rf "/home/$U"
    rm -rf "$BASE" /var/aixmcp
    print "removed user $U, $BASE, /var/aixmcp and $RULE"
    exit 0
fi

here=$(cd "$(dirname "$0")" && pwd)
[[ -f $here/dispatch && -f $here/aix_storage_paths.ksh ]] || { print "dispatch and aix_storage_paths.ksh must be next to this script"; exit 1; }
[[ -s $KEY ]] || { print "-k <public key file> is required"; exit 1; }
[[ -n $FROM && $FROM == +([0-9A-Za-z.:,/*-]) ]] || { print "-f <management host list for from=\"...\"> is required"; exit 1; }
egrep -q '^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp[0-9]+) [A-Za-z0-9+/=]+' "$KEY" || { print "$KEY does not look like one OpenSSH public key"; exit 1; }
whence -q sudo || { print "sudo not found (AIX Toolbox); install it or use the RBAC setup in docs/live-collection.md"; exit 1; }

# 1. user: no password (key only), not in any admin group
if ! lsuser "$U" >/dev/null 2>&1; then
    mkuser pgrp=staff groups=staff home=/home/$U shell=/usr/bin/ksh gecos="aix-mcp collection (read-only)" "$U" || exit 1
fi
# 2. files
mkdir -p $BASE/bin $BASE/libexec
cp "$here/dispatch" $BASE/bin/dispatch
cp "$here/aix_storage_paths.ksh" $COLL
chown -R root:system $BASE; chmod 755 $BASE $BASE/bin $BASE/libexec $BASE/bin/dispatch $COLL
# 3. host-side evidence store
mkdir -p $STORE; chown root:system /var/aixmcp $STORE; chmod 700 /var/aixmcp $STORE
# 4. key, forced command only
h=/home/$U
mkdir -p $h/.ssh
print -- "command=\"$BASE/bin/dispatch\",restrict,from=\"$FROM\" $(head -1 "$KEY")" > $h/.ssh/authorized_keys
chown -R "$U":staff $h/.ssh; chmod 700 $h/.ssh; chmod 600 $h/.ssh/authorized_keys
# 5. one exact sudo rule
mkdir -p $SUDOERS_D; chmod 750 $SUDOERS_D
tmp=$(dirname "$RULE")/.aixmcp.$$
cat > "$tmp" <<EOF
# aix-mcp: $U may run the read-only storage collector as root, with these exact arguments only.
Defaults:$U !requiretty, env_reset
$U ALL=(root) NOPASSWD: $COLL -k -o $STORE, $COLL -k -q -o $STORE
EOF
chmod 440 "$tmp"
if visudo -c -f "$tmp" >/dev/null; then mv "$tmp" "$RULE"; else rm -f "$tmp"; print "sudo rule failed visudo check"; exit 1; fi
grep -q "^[@#]includedir $SUDOERS_D" "$SUDOERS" 2>/dev/null || \
    print "NOTE: $SUDOERS has no '@includedir $SUDOERS_D' line; add it with visudo or the rule is not used."

print "installed: user $U, $BASE/bin/dispatch, $COLL, $STORE, sudo rule $RULE"
print "test from a management host:  ssh -i <key> $U@<this host> version"
