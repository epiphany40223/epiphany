#!/bin/bash

set -euo pipefail

orig=cookies.sqlite3
copy=copy-cookies.sqlite3

server_name=api.epiphanycatholicchurch.org
server_location=stewardship-2026-data

if test -x /bin/true; then
    true=/bin/true
elif test -x /usr/bin/true; then
    true=/usr/bin/true
else
    echo "Cannot find the 'true' executable"
    exit 1
fi

while (eval $true) do
    echo "=== `date`"

    cp $orig $copy
    echo zstd compressing...
    zstd --rm $copy
    echo scping...
    scp $copy.zst ${server_name}:$server_location/$copy.zst
    echo zstd decompressing...
    ssh $server_name zstd --rm -d $server_location/$copy.zst
    echo moving...
    ssh $server_name mv $server_location/$copy $server_location/$orig

    rm -f $copy.zst

    echo "Sleeping..."
    sleep 5
done
