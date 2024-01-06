#!/bin/bash

set -euo pipefail

orig=cookies.sqlite3
copy=copy-cookies.sqlite3

server_name=api.epiphanycatholicchurch.org
server_location=stewardship-2024-data

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
    echo bzipping...
    bzip2 -f $copy
    echo scping...
    scp $copy.bz2 ${server_name}:$server_location/$copy.bz2
    echo bunzipping...
    ssh $server_name bunzip2 -f $server_location/$copy.bz2
    echo moving...
    ssh $server_name mv $server_location/$copy $server_location/$orig

    echo "Sleeping..."
    sleep 5
done
