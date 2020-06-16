#!/bin/zsh

orig=cookies.sqlite3
copy=copy-cookies.sqlite3

server_name=api.epiphanycatholicchurch.org
server_location=census-2020-data

id="-i $HOME/.ssh/ecc-census2020-droplet"

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
    eval scp $id $copy ${server_name}:$server_location/$copy
    eval ssh $id $server_name mv $server_location/$copy $server_location/$orig

    echo "Sleeping..."
    sleep 5
done
