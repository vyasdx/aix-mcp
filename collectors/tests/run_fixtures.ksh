#!/usr/bin/ksh93
# Runs collectors/aix_storage_paths.ksh against the synthetic fixtures and checks the
# expected lines. Needs ksh93 and the AIX userland (awk, ps); run it on any AIX host as root.
# It only reads fixtures and writes under /tmp/aixmcp_fixture_<pid>.
here=$(cd "$(dirname "$0")" && pwd)
script=$here/../aix_storage_paths.ksh
work=/tmp/aixmcp_fixture_$$
mkdir -p $work && cp "$here/stub" $work/stub && chmod 755 $work/stub
BASE="hostname oslevel uname lsattr lsdev lspv lspath lsmpio lscfg bootinfo fcstat mount df lssrc manage_disk_drivers exportfs"
fail=0
for scen in "$here"/fixtures/*; do
    name=${scen##*/}
    bin=$work/$name/bin; mkdir -p $bin
    stubs=$BASE
    for c in powermt pcmpath dlnkmgr vxdmpadm ioscli; do
        ls "$scen"/${c}_* >/dev/null 2>&1 && stubs="$stubs $c"
    done
    for c in $stubs; do ln -s $work/stub $bin/$c; done
    ios=/nonexistent; [[ -e $bin/ioscli ]] && ios=$bin/ioscli
    exp=/nonexistent; [[ -f $scen/exports ]] && exp=$scen/exports
    AIXMCP_TEST_BIN=$bin AIXMCP_FIXTURE=$scen AIXMCP_IOSCLI=$ios AIXMCP_EXPORTS=$exp \
        /usr/bin/ksh93 "$script" -o $work/$name/out -t 3 -b 60 > $work/$name/summary.txt 2> $work/$name/stderr.txt
    n=0; bad=0
    while IFS= read -r pat; do
        [[ -z $pat || $pat == \#* ]] && continue
        (( n += 1 ))
        if ! grep -q -- "$pat" $work/$name/summary.txt $work/$name/out/*.kh; then
            print "  FAIL [$name] expected: $pat"; (( bad += 1 ))
        fi
    done < "$scen/expect"
    if [[ -f $scen/expect_not ]]; then
        while IFS= read -r pat; do
            [[ -z $pat ]] && continue
            (( n += 1 ))
            if grep -q -- "$pat" $work/$name/out/*.kh; then
                print "  FAIL [$name] must not appear: $pat"; (( bad += 1 ))
            fi
        done < "$scen/expect_not"
    fi
    if (( bad )); then fail=1; print "$name: $bad of $n checks failed (see $work/$name)"
    else print "$name: $n checks passed"; fi
done
(( fail )) || print "ALL PASSED"
print "Output kept in $work"
exit $fail
