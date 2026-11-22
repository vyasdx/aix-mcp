#!/usr/bin/ksh93
# aix_storage_paths.ksh  v0.1
# Read-only storage, multipath and mapping collector for an AIX LPAR or a VIOS.
# Part of aix-mcp (https://github.com/vyasdx/aix-mcp). Apache-2.0. Not affiliated with IBM.
# Design and safety rules: docs/design.md and docs/commands.md.
#
# What it promises
#   - Read-only. It runs list and query commands only (allowlist in ALLOW below) and
#     writes only into its own output directory. No ODM changes, no cfgmgr, no I/O tests.
#   - Never reads inside a remote client mount (NFS, CIFS, autofs and other network or
#     unknown filesystems). They are listed from the kernel mount table only: no df,
#     ls, stat or find on them.
#   - NFS server: exported paths on LOCAL filesystems get capacity only. File contents
#     are never read, local or remote.
#   - Multipath: detects the driver first (AIX PCM, SDDPCM, PowerPath, HDLM, Veritas DMP),
#     then runs only that driver's query commands.
#   - VIOS: when /usr/ios/cli/ioscli exists it also collects NPIV (lsmap -npiv, lsnports),
#     vSCSI (lsmap) and SEA mappings through ioscli.
#   - Every command runs under a watchdog. If it is slow, hung or stale it is killed when
#     possible, abandoned (never waited on) and recorded as MISSING, with the command to
#     run by hand. A whole-run time budget stops new checks when it is used up.
#   - Runs at low priority (renice 19).
#
# Usage: aix_storage_paths.ksh [-o dir] [-t secs] [-b secs] [-q] [-v]
#   -o dir   output directory (default /tmp/aixmcp_storage)
#   -t secs  per-check timeout (default 10)
#   -b secs  whole-run budget (default 120)
#   -q       quick: ODM and driver tables only; skip per-disk size and fcstat (device queries)
#   -v       also print per-disk path detail
#
# Output
#   <dir>/<host>_storage_<UTC>.kh    pipe-delimited records (layout at the end of this file)
#   <dir>/<host>_storage_<UTC>.raw/  raw output of every command, for evidence
#   stdout                           compact summary, notes and the MISSING list
#
# The .kh file holds host names, WWPNs and LUN ids. Keep it on the management tier;
# pseudonymise it before it leaves the site.

VERSION=0.1
PATH=${AIXMCP_TEST_BIN:+$AIXMCP_TEST_BIN:}/usr/bin:/usr/sbin:/etc:/usr/ios/cli:/usr/lpp/EMC/Symmetrix/bin:/usr/DynamicLinkManager/bin:$PATH
export PATH LANG=C LC_ALL=C

OUTDIR=/tmp/aixmcp_storage
TMO=10
BUDGET=120
QUICK=0
VERBOSE=0
while getopts "o:t:b:qv" opt; do
    case $opt in
        o) OUTDIR=$OPTARG ;;
        t) TMO=$OPTARG ;;
        b) BUDGET=$OPTARG ;;
        q) QUICK=1 ;;
        v) VERBOSE=1 ;;
        *) sed -n '2,40p' "$0"; exit 1 ;;
    esac
done

(( $(id -u) == 0 )) || { echo "Run as root (read-only commands, but lsattr/lsmpio/ioscli need it)."; exit 1; }

typeset -F3 SECONDS
START=$SECONDS
HOST=$(hostname 2>/dev/null)
HOST=${HOST%%.*}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BASE=$OUTDIR/${HOST}_storage_$STAMP
OUT=$BASE.kh
RAW=$BASE.raw
umask 077
mkdir -p "$RAW" || { echo "Cannot create $RAW"; exit 1; }
: > "$OUT"
renice -n 19 -p $$ >/dev/null 2>&1

# Commands this script may run (first word). Anything else is refused.
ALLOW=" hostname oslevel uname lsattr lsdev lspv lspath lsmpio lscfg bootinfo fcstat mount df exportfs cat \
 lslpp manage_disk_drivers lssrc powermt pcmpath dlnkmgr vxdmpadm ioscli ps "

NCHK=0; NOK=0; NMISS=0; NNA=0
MISSING_LIST=""

function rec {   # rec TYPE field...   one record line; '|' inside a field becomes '/'
    typeset line="$1" f
    shift
    for f in "$@"; do line="$line|${f//\|//}"; done
    print -r -- "$line" >> "$OUT"
}

function killtree {   # killtree PID SIGNAL : signal a process and all its descendants
    typeset p=$1 sig=$2 kids k
    kids=$(ps -e -o pid= -o ppid= 2>/dev/null | awk -v pp="$p" '$2==pp {print $1}')
    for k in $kids; do killtree "$k" "$sig"; done
    kill -"$sig" "$p" 2>/dev/null
}

# run ID TIMEOUT COMMAND...  -> raw output in $RAW/ID.out; returns 0 ok, 1 cmd error, 2 missing
function run {
    typeset id=$1 tmo=$2
    shift 2
    typeset cmd="$*" first=${1##*/}
    typeset out=$RAW/$id.out err=$RAW/$id.err
    typeset -F3 t0 el left
    (( NCHK += 1 ))
    if [[ $ALLOW != *" $first "* ]]; then
        rec C "$id" REFUSED 0 - "command not in allowlist" "$cmd"
        return 2
    fi
    (( left = BUDGET - (SECONDS - START) ))
    if (( left <= 0 )); then
        (( NMISS += 1 )); MISSING_LIST="$MISSING_LIST$id|budget|$cmd\n"
        rec C "$id" MISSING 0 - "run budget ${BUDGET}s used up; not started" "$cmd"
        return 2
    fi
    (( tmo > left )) && tmo=$left
    t0=$SECONDS
    "$@" >"$out" 2>"$err" </dev/null &
    typeset pid=$! d=0.005
    while kill -0 "$pid" 2>/dev/null; do
        if (( SECONDS - t0 >= tmo )); then
            killtree "$pid" TERM; sleep 0.2; killtree "$pid" KILL
            disown "$pid" 2>/dev/null
            (( el = SECONDS - t0 ))
            (( NMISS += 1 )); MISSING_LIST="$MISSING_LIST$id|timeout ${tmo}s|$cmd\n"
            rec C "$id" MISSING "$el" - "no answer in ${tmo}s (slow, hung or stale); abandoned, check by hand" "$cmd"
            return 2
        fi
        sleep $d
        (( d < 0.2 )) && (( d = d * 2 ))
    done
    wait "$pid"; typeset rc=$?
    (( el = SECONDS - t0 ))
    if (( rc == 0 )); then
        (( NOK += 1 )); rec C "$id" OK "$el" 0 - "$cmd"; return 0
    fi
    (( NOK += 1 ))
    rec C "$id" ERROR "$el" "$rc" "$(head -1 "$err" 2>/dev/null)" "$cmd"
    return 1
}

function na {   # na ID REASON : check not applicable on this host
    (( NCHK += 1 )); (( NNA += 1 ))
    rec C "$1" NA 0 - "$2" -
}

function note { rec O "$1" "$2"; NOTES="$NOTES$1: $2\n"; }
NOTES=""

# ---------------------------------------------------------------- host and role
run oslevel 5 oslevel -s
run uname 5 uname -L
run sys0 5 lsattr -El sys0 -a modelname -a systemid -F value
ROLE=LPAR
IOS=""
IOSCLI=${AIXMCP_IOSCLI:-/usr/ios/cli/ioscli}   # AIXMCP_IOSCLI, AIXMCP_EXPORTS, AIXMCP_TEST_BIN: fixture tests only
if [[ -x $IOSCLI ]]; then ROLE=VIOS; IOS=$IOSCLI; fi
rec H collector aix_storage_paths.ksh
rec H version $VERSION
rec H host "$HOST"
rec H role $ROLE
rec H collected_at "$STAMP"
rec H oslevel "$(head -1 $RAW/oslevel.out 2>/dev/null)"
rec H lpar "$(cat $RAW/uname.out 2>/dev/null)"
rec H model_serial "$(tr '\n' ' ' < $RAW/sys0.out 2>/dev/null)"
rec H options "timeout=$TMO budget=$BUDGET quick=$QUICK"

# ---------------------------------------------------------------- mounts (kernel table only)
# Local filesystems get df. Remote client mounts are listed and never touched.
LOCAL_MPS=""; CLUSTER_MPS=""
NLOCAL=0; NREMOTE=0; NCLUSTER=0; NPSEUDO=0; NOTHER=0
typeset -A MPCLASS
if run mount 5 mount; then
    awk 'NR>2 && NF>=3 {
            if (substr($0,1,1) ~ /[ \t]/) print "|" $1 "|" $2 "|" $3;
            else print $1 "|" $2 "|" $3 "|" $4 }' $RAW/mount.out > $RAW/mount.parsed
    while IFS='|' read -r node dev mp vfs; do
        case $vfs in
            jfs2|jfs)                     class=local;   action="capacity" ;;
            procfs|ahafs|namefs|cdrfs|udfs) class=pseudo; action="not read" ;;
            mmfs)                         class=cluster; action="capacity (own watchdog)" ;;
            nfs|nfs3|nfs4|stnfs|cifs|smbfs|autofs|sfs|nfsv4)
                                          class=remote;  action="not read (client mount; data belongs to the server)" ;;
            *)                            class=other;   action="not read (unknown filesystem type)" ;;
        esac
        MPCLASS[$mp]=$class
        rec M "$mp" "$dev" "$vfs" "$class" "${node:--}" "$action"
        case $class in
            local)   LOCAL_MPS="$LOCAL_MPS $mp"; (( NLOCAL += 1 )) ;;
            cluster) CLUSTER_MPS="$CLUSTER_MPS $mp"; (( NCLUSTER += 1 )) ;;
            remote)  (( NREMOTE += 1 )) ;;
            pseudo)  (( NPSEUDO += 1 )) ;;
            *)       (( NOTHER += 1 )) ;;
        esac
    done < $RAW/mount.parsed
fi
(( NREMOTE > 0 )) && note mounts "$NREMOTE remote client mount(s) listed from the mount table only; contents and capacity not read by design"
(( NOTHER > 0 ))  && note mounts "$NOTHER mount(s) of unknown type not read; review the M records"

if [[ -n $LOCAL_MPS ]]; then
    run df_local "$TMO" df -k $LOCAL_MPS
    awk 'NR>1 && $2 ~ /^[0-9]/ {u=$4; sub("%","",u); printf "F|%s|%d|%d|%s|local\n", $7, $2/1024, $3/1024, u}' \
        $RAW/df_local.out >> "$OUT" 2>/dev/null
fi
i=0
for mp in $CLUSTER_MPS; do
    (( i += 1 ))
    if run df_cluster_$i 5 df -k "$mp"; then
        awk 'NR>1 && $2 ~ /^[0-9]/ {u=$4; sub("%","",u); printf "F|%s|%d|%d|%s|cluster\n", $7, $2/1024, $3/1024, u}' \
            $RAW/df_cluster_$i.out >> "$OUT"
    fi
done

# ---------------------------------------------------------------- NFS server exports
NFS_SERVER=no
NEXPORT=0
run nfs_subsys 5 lssrc -g nfs
EXPORTS=${AIXMCP_EXPORTS:-/etc/exports}
if [[ -s $EXPORTS || ( -z $AIXMCP_EXPORTS && -s /etc/xtab ) ]]; then
    run exports_file 5 cat "$EXPORTS"
    run exportfs 5 exportfs
    grep -q "^ *nfsd .*active" $RAW/nfs_subsys.out 2>/dev/null && NFS_SERVER=yes
    # exported path -> containing mount (longest prefix) -> class
    src=exports_file
    [[ -s $RAW/exportfs.out ]] && src=exportfs
    touch $RAW/$src.out
    while read -r xp xopts; do
        [[ $xp == /* ]] || continue
        best=""
        for mp in "${!MPCLASS[@]}"; do
            if [[ $xp == "$mp" || $xp == "$mp"/* || $mp == / ]]; then
                (( ${#mp} > ${#best} )) && best=$mp
            fi
        done
        cls=${MPCLASS[$best]:-unknown}
        if [[ $cls == local ]]; then act="capacity of $best only; contents not read"
        else act="not read ($cls)"; fi
        rec X "$xp" "${best:--}" "$cls" "$act" "${xopts:--}"
        (( NEXPORT += 1 ))
    done < $RAW/$src.out
else
    na exportfs "no /etc/exports or /etc/xtab"
fi
rec H nfs_server "$NFS_SERVER exports=$NEXPORT"

# ---------------------------------------------------------------- disks, PVs, paths (ODM and driver tables)
run disks 10 lsdev -Cc disk -F "name:status:location:description"
run lspv 10 lspv
run lspath "$TMO" lspath -F "name:parent:connection:path_status:status"
if whence -q lsmpio; then
    run lsmpio "$TMO" lsmpio
    run lsmpio_ar "$TMO" lsmpio -ar
else
    na lsmpio "lsmpio not present (AIX PCM table not available)"
fi
run mdd 5 manage_disk_drivers -l

DISKS=$(awk -F: '{print $1}' $RAW/disks.out 2>/dev/null)
NDISK=$(print -r -- "$DISKS" | grep -c .)

# all attributes of every disk in one pass (ODM read; scaled timeout)
function dattr { typeset d; for d in $DISKS; do print "### $d"; lsattr -El "$d" -F "attribute value" 2>&1; done; }
ALLOW="$ALLOW dattr "
run disk_attrs $(( TMO + NDISK / 5 )) dattr

# per-disk size: opens the device, so each disk has its own short watchdog and a breaker
typeset -A SIZE
if (( QUICK == 0 )); then
    fails=0
    for d in $DISKS; do
        if (( fails >= 3 )); then
            (( NCHK += 1 )); (( NMISS += 1 )); MISSING_LIST="${MISSING_LIST}size_$d|skipped after 3 timeouts|bootinfo -s $d\n"
            rec C "size_$d" MISSING 0 - "skipped: 3 disks already timed out" "bootinfo -s $d"
            continue
        fi
        if run "size_$d" 3 bootinfo -s "$d"; then
            SIZE[$d]=$(head -1 $RAW/size_$d.out); fails=0
        else
            (( fails += 1 ))
        fi
    done
else
    na disk_sizes "quick mode (-q)"
fi

# third-party multipath drivers: detect, then query only what is present
MP_DRIVERS=""
has_pp=0; has_sdd=0; has_hdlm=0; has_dmp=0
whence -q powermt  && has_pp=1
whence -q pcmpath  && has_sdd=1
whence -q dlnkmgr  && has_hdlm=1
whence -q vxdmpadm && has_dmp=1
if (( has_pp )); then
    MP_DRIVERS="$MP_DRIVERS PowerPath"
    run powermt 30 powermt display dev=all
    run powermt_paths 15 powermt display paths
fi
if (( has_sdd )); then
    MP_DRIVERS="$MP_DRIVERS SDDPCM"
    run pcmpath_dev 30 pcmpath query device
    run pcmpath_ad 15 pcmpath query adapter
    note multipath "SDDPCM is installed; IBM has withdrawn SDDPCM support, confirm the plan to move to AIX PCM"
fi
if (( has_hdlm )); then
    MP_DRIVERS="$MP_DRIVERS HDLM"
    run dlnkmgr 30 dlnkmgr view -path
fi
if (( has_dmp )); then
    MP_DRIVERS="$MP_DRIVERS DMP"
    run vxdmp_ctlr 15 vxdmpadm listctlr all
    run vxdmp_paths 30 vxdmpadm getsubpaths
fi
(( has_pp + has_sdd + has_hdlm + has_dmp == 0 )) && na thirdparty_mp "no PowerPath, SDDPCM, HDLM or DMP commands found"
# third-party path health: count bad paths in each driver's own view (raw output kept as evidence)
function badpaths {   # badpaths DRIVER RAWFILE EGREP-PATTERN
    typeset c
    [[ -s $RAW/$2 ]] || return
    c=$(egrep -c "$3" $RAW/$2)
    (( c > 0 )) && note multipath "$1 reports $c dead/failed/offline path(s); see raw/$2"
}
(( has_pp ))   && badpaths PowerPath powermt.out '[[:space:]](dead|unlic)[[:space:]]'
(( has_sdd ))  && badpaths SDDPCM pcmpath_dev.out '[[:space:]](DEAD|FAILED|CLOSE_DEAD|INVALID)[[:space:]]'
(( has_hdlm )) && badpaths HDLM dlnkmgr.out 'Offline'
(( has_dmp ))  && badpaths DMP vxdmp_paths.out 'DISABLED'

# build the D (disk) and P (path) records
typeset -A VG PVID PT PE PF PO OPT ATTR
while read -r n pvid vg st rest; do
    PVID[$n]=$pvid; VG[$n]=$vg
    [[ $st == concurrent ]] && VG[$n]="$vg(concurrent)"
done < $RAW/lspv.out 2>/dev/null
while IFS=: read -r n parent conn pst st; do
    [[ -n $n ]] || continue
    (( PT[$n] += 1 ))
    case $st in
        Enabled) (( PE[$n] += 1 )) ;;
        Failed)  (( PF[$n] += 1 )) ;;
        *)       (( PO[$n] += 1 )) ;;
    esac
    rec P "$n" "$parent" "$conn" "$pst" "$st"
done < $RAW/lspath.out 2>/dev/null
if [[ -s $RAW/lsmpio.out ]]; then
    while read -r n pid st pst rest; do
        [[ $pst == *Opt* ]] && (( OPT[$n] += 1 ))
    done < $RAW/lsmpio.out
fi
cur=""
while read -r a v rest; do
    if [[ $a == "###" ]]; then cur=$v; continue; fi
    [[ -n $cur ]] && ATTR[$cur.$a]=$v
done < $RAW/disk_attrs.out 2>/dev/null

NPATH_BAD=0; NSINGLE=0; NHC0=0
while IFS=: read -r n st loc desc; do
    [[ -n $n ]] || continue
    pcm=${ATTR[$n.PCM]:--}
    case $pcm in
        *sddpcm*)       drv=SDDPCM ;;
        PCM/friend/*)   drv="AIX PCM" ;;
        -)  case "$n $desc" in
                hdiskpower*)    drv="PowerPath pseudo" ;;
                *[Pp]ower[Pp]ath*|*EMC*) drv="PowerPath member/non-MPIO" ;;
                *Hitachi*|*HDLM*) drv="HDLM/non-MPIO" ;;
                *)              drv="non-MPIO" ;;
            esac ;;
        *)  drv="other PCM" ;;
    esac
    t=${PT[$n]:-0}; e=${PE[$n]:-0}; f=${PF[$n]:-0}; o=${PO[$n]:-0}
    hc=${ATTR[$n.hcheck_interval]:--}
    rec D "$n" "$st" "${loc:--}" "${VG[$n]:-None}" "${PVID[$n]:-none}" "${SIZE[$n]:--}" "$pcm" \
        "${ATTR[$n.algorithm]:--}" "${ATTR[$n.reserve_policy]:--}" "${ATTR[$n.queue_depth]:--}" "$hc" \
        "$t" "$e" "$f" "$o" "${OPT[$n]:--}" "$drv" "$desc"
    if (( f + o > 0 )); then
        (( NPATH_BAD += 1 )); note "$n" "$f failed and $o other non-enabled path(s) of $t"
    fi
    if [[ $drv == "AIX PCM" ]] && (( t == 1 )); then
        (( NSINGLE += 1 )); note "$n" "only one path"
    fi
    if [[ $drv == "AIX PCM" && $hc == 0 ]]; then
        (( NHC0 += 1 )); note "$n" "hcheck_interval=0: failed paths are not health-checked back"
    fi
    if [[ ${VG[$n]} == *concurrent* && ${ATTR[$n.reserve_policy]} != no_reserve && ${ATTR[$n.reserve_policy]} != - ]]; then
        note "$n" "concurrent VG member with reserve_policy=${ATTR[$n.reserve_policy]}"
    fi
done < $RAW/disks.out 2>/dev/null
NATIVE=$(grep -c '^D|.*|AIX PCM|' "$OUT")
(( NATIVE > 0 )) && MP_DRIVERS="AIX-PCM$MP_DRIVERS"
rec H multipath "${MP_DRIVERS:-none detected}"

# lsmpio -ar: FC adapter -> storage target ports
if [[ -s $RAW/lsmpio_ar.out ]]; then
    awk '/^Adapter Driver:/ {a=$3; w="-"; l="-"}
         /Adapter WWPN:/ {w=$3}
         /Link State:/ {l=$3}
         $1 ~ /^[0-9a-fA-F]+$/ && length($1)==16 && NF>=6 {printf "T|%s|%s|%s|%s|%s|%s|%s|%s|%s\n", a, w, l, $1, $2, $3, $4, $5, $6}' \
        $RAW/lsmpio_ar.out >> "$OUT"
fi

# ---------------------------------------------------------------- adapters: FC, vSCSI, (VIOS) vfchost
run adapters 10 lsdev -Cc adapter -F "name:status:location:description"
FCS=$(awk -F: '$1 ~ /^fcs[0-9]+$/ {print $1}' $RAW/adapters.out 2>/dev/null)
function aattr {
    typeset a c
    for a in $FCS; do
        print "### $a"; lscfg -vl "$a" 2>&1 | grep -i "network address"
        c=$(lsdev -p "$a" -F name 2>/dev/null | grep '^fscsi' | head -1)
        [[ -n $c ]] && { print "#fscsi $c"; lsattr -El "$c" -F "attribute value" 2>&1 | egrep '^(fc_err_recov|dyntrk|attach) '; }
    done
}
ALLOW="$ALLOW aattr "
[[ -n $FCS ]] && run fc_attrs $(( TMO + 5 )) aattr
typeset -A WWPN FSCSI FERR DYN
cur=""
while read -r a b c; do
    case $a in
        "###")    cur=$b ;;
        "#fscsi") FSCSI[$cur]=$b ;;
        Network)  WWPN[$cur]=${b##*.} ;;
        fc_err_recov) FERR[$cur]=$b ;;
        dyntrk)   DYN[$cur]=$b ;;
    esac
done < $RAW/fc_attrs.out 2>/dev/null
while IFS=: read -r n st loc desc; do
    case $n in
        fcs*)    kind=fc
                 [[ $desc == *Virtual* ]] && kind="virtual fc (NPIV client)" ;;
        vscsi*)  kind="virtual scsi client" ;;
        vfchost*) kind="vfchost (VIOS NPIV server)" ;;
        vhost*)  kind="vhost (VIOS vSCSI server)" ;;
        ent*|sissas*|hdcrypt|pkcs11|vsa*) continue ;;
        *)       kind=other ;;
    esac
    w=${WWPN[$n]:--}
    rec A "$n" "$st" "${loc:--}" "$kind" "${w:--}" "${FSCSI[$n]:--}" "${FERR[$n]:--}" "${DYN[$n]:--}" "$desc"
    if [[ $n == fcs* ]]; then
        [[ -n ${FERR[$n]} && ${FERR[$n]} != fast_fail ]] && note "${FSCSI[$n]}" "fc_err_recov=${FERR[$n]} (fast_fail is the usual setting with multipath)"
        [[ -n ${DYN[$n]} && ${DYN[$n]} != yes ]] && note "${FSCSI[$n]}" "dyntrk=${DYN[$n]} (yes lets paths survive fabric N_Port ID changes)"
    fi
done < $RAW/adapters.out 2>/dev/null

if (( QUICK == 0 )); then
    for a in $FCS; do
        if run "fcstat_$a" 5 fcstat "$a"; then
            sp=$(sed -n 's/^Port Speed (running): *//p' $RAW/fcstat_$a.out | head -1)
            pt=$(sed -n 's/^Port Type: *//p' $RAW/fcstat_$a.out | head -1)
            at=$(sed -n 's/^Attention Type: *//p' $RAW/fcstat_$a.out | head -1)
            rec L "$a" "${sp:--}" "${pt:--}" "${at:--}"
        fi
    done
else
    na fcstat "quick mode (-q)"
fi

# ---------------------------------------------------------------- VIOS mappings (ioscli)
if [[ $ROLE == VIOS ]]; then
    run ioslevel 10 $IOS ioslevel
    rec H ioslevel "$(head -1 $RAW/ioslevel.out 2>/dev/null)"
    run npiv 30 $IOS lsmap -all -npiv -field name physloc clntid clntname clntos status fc fcphysloc ports flags vfcclient vfcclientdrc -fmt :
    run lsnports 15 $IOS lsnports
    run vscsi 30 $IOS lsmap -all -field svsa physloc clientid vtd status lun backing bdphys -fmt :
    run sea 15 $IOS lsmap -all -net -fmt :
    # N: vfchost -> client LPAR -> physical FC port
    awk -F: 'NF>=6 {printf "N|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s\n", $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12}' \
        $RAW/npiv.out >> "$OUT" 2>/dev/null
    # V: vhost -> client id -> one record per VTD (groups of 5 fields after the first 3)
    awk -F: 'NF>=3 { if (NF==3) {printf "V|%s|%s|%s|-|-|-|-|-\n",$1,$2,$3; next}
                     for (i=4; i+4<=NF; i+=5) printf "V|%s|%s|%s|%s|%s|%s|%s|%s\n",$1,$2,$3,$i,$(i+1),$(i+2),$(i+3),$(i+4) }' \
        $RAW/vscsi.out >> "$OUT" 2>/dev/null
    # Q: lsnports  name physloc fabric tports aports swwpns awwpns
    awk 'NR>1 && $1 ~ /^fcs/ {printf "Q|%s|%s|%s|%s|%s|%s|%s\n",$1,$2,$3,$4,$5,$6,$7}' $RAW/lsnports.out >> "$OUT" 2>/dev/null
    grep '^N|' "$OUT" | awk -F'|' '$7 != "LOGGED_IN" {print $2" client "$4" ("$5") status "$7}' | while read -r l; do
        note vios "vfchost not logged in: $l"
    done
    grep '^Q|' "$OUT" | awk -F'|' '$4 != "1" {print $2" fabric="$4}' | while read -r l; do
        note vios "FC port without NPIV fabric support: $l"
    done
else
    na vios "not a VIOS (no /usr/ios/cli/ioscli)"
fi

# ---------------------------------------------------------------- lab self-test of the watchdog
# AIXMCP_SELFTEST_HANG=<path> makes one deliberate 'df' on that path so a lab can prove a hung
# command is abandoned and marked MISSING. Never set it on a production host.
if [[ -n $AIXMCP_SELFTEST_HANG ]]; then
    run selftest_hang 5 df -k "$AIXMCP_SELFTEST_HANG"
fi

# ---------------------------------------------------------------- summary
typeset -F1 TOTAL
(( TOTAL = SECONDS - START ))
rec H elapsed_s "$TOTAL"
rec H checks "total=$NCHK ok=$NOK missing=$NMISS na=$NNA"

print "Host $HOST  role $ROLE  AIX $(head -1 $RAW/oslevel.out 2>/dev/null)  multipath: ${MP_DRIVERS:-none detected}"
print "Mounts: $NLOCAL local, $NCLUSTER cluster, $NREMOTE remote client (not read), $NPSEUDO pseudo, $NOTHER other (not read)   NFS server: $NFS_SERVER, exports $NEXPORT"
print
printf "%-10s %-14s %7s %-10s %-14s %-11s %3s %4s %5s %4s %s\n" DISK VG SIZE_GB DRIVER ALGORITHM RESERVE QD HCHK PATHS OPT STATUS
grep '^D|' "$OUT" | awk -F'|' '{
    sz = ($7 ~ /^[0-9]+$/) ? sprintf("%.0f", $7/1024) : "-"
    drv = $18; if (drv == "AIX PCM") drv = "AIX-PCM"
    paths = $14 "/" $13
    st = ($15+$16 > 0) ? "PATHS!" : ($3 == "Available" ? "ok" : $3)
    printf "%-10s %-14s %7s %-10s %-14s %-11s %3s %4s %5s %4s %s\n", $2, $5, sz, substr(drv,1,10), $9, $10, $11, $12, paths, $17, st }'
print
grep '^A|' "$OUT" | grep -E '^A\|fcs|^A\|vfchost|^A\|vscsi|^A\|vhost' | awk -F'|' '{printf "%-9s %-28s %-17s %-8s err=%s dyntrk=%s\n", $2, $5, $6, $7, $8, $9}'
grep '^L|' "$OUT" | awk -F'|' '{printf "  %s link: %s, %s, attention %s\n", $2, $3, $4, $5}'
if [[ $ROLE == VIOS ]]; then
    print
    print "NPIV: $(grep -c '^N|' "$OUT") vfchost  vSCSI: $(grep '^V|' "$OUT" | cut -d'|' -f2 | sort -u | grep -c .) vhost, $(grep '^V|' "$OUT" | awk -F'|' '$5!="-"' | grep -c .) VTD  NPIV ports: $(grep -c '^Q|' "$OUT")"
fi
if (( VERBOSE )); then
    print; print "Paths (disk parent connection path_status status)"
    grep '^P|' "$OUT" | awk -F'|' '{printf "  %-10s %-8s %-30s %-10s %s\n",$2,$3,$4,$5,$6}'
fi
print
print "### Notes"
if [[ -n $NOTES ]]; then print -n -- "$NOTES" | sed 's/^/- /'; else print -- "- none"; fi
print
print "### Checks: $NCHK run, $NOK answered, $NMISS MISSING, $NNA not applicable, ${TOTAL}s"
if (( NMISS > 0 )); then
    print "MISSING: check these by hand if the data is needed"
    print -n -- "$MISSING_LIST" | awk -F'|' '{printf "- %-16s %-24s %s\n", $1, $2, $3}'
fi
print
print "Records: $OUT"
print "Raw:     $RAW/"
exit 0

# ---------------------------------------------------------------- record layout (.kh)
# H|key|value                                    header (host, role, oslevel, multipath, options...)
# C|check|status|secs|rc|reason|command          one per command: OK, ERROR, MISSING, NA, REFUSED
# M|mountpoint|device|vfs|class|node|action      class: local, cluster, remote, pseudo, other
# F|mountpoint|size_mb|free_mb|used_pct|class    capacity, local and cluster filesystems only
# X|export|fs_mountpoint|fs_class|action|options NFS server exports
# D|disk|status|location|vg|pvid|size_mb|pcm|algorithm|reserve|queue_depth|hcheck|paths|enabled|failed|other|optimised|driver|description
# P|disk|parent|connection|path_status|status    one per path (lspath)
# T|fscsi|adapter_wwpn|link|remote_port|enabled|disabled|failed|missing|port_id   (lsmpio -ar)
# A|adapter|status|location|kind|wwpn|fscsi|fc_err_recov|dyntrk|description
# L|fcs|speed|port_type|attention                fcstat
# N|vfchost|physloc|client_id|client_name|client_os|status|fc|fc_physloc|ports|flags|vfc_client|vfc_drc   (VIOS)
# V|vhost|physloc|client_id|vtd|status|lun|backing|backing_physloc                                       (VIOS)
# Q|fcs|physloc|fabric|tports|aports|swwpns|awwpns                                                         (VIOS lsnports)
# O|subject|note                                 observations, not verdicts
