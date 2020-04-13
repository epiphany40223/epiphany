#!/bin/zsh

orig=cookies.sqlite3
copy=copy-cookies.sqlite3

server_name=redirect.epiphanycatholicchurch.org
server_location=stewardship-2020-data

if test -x /bin/true; then
    true=/bin/true
elif test -x /usr/bin/true; then
    true=/usr/bin/true
else
    echo "Cannot find the 'true' executable"
    exit 1
fi

while (eval $true) do
    echo "=== scp'ing at `date`"

    cp $orig $copy
    scp $copy ${server_name}:$server_location/$copy
    ssh $server_name mv $server_location/$copy $server_location/$orig

    echo "Sleeping..."
    sleep 5
done
