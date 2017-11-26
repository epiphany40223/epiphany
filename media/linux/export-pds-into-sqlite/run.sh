#!/bin/zsh

set -x

pds_input_dir=/mnt/hgfs/pdschurch/Data

base=/home/itadmin/git/epiphany/media/linux
prog_dir=$base/export-pds-into-sqlite
logfile=$base/logfile.txt
sqlite_out_dir=$base/pds-data

cd $prog_dir

./export-pdschurchoffice-to-sqlite3.py \
    --pxview=/usr/local/bin/pxview \
    --verbose \
    --out-dir=$sqlite_out_dir \
    --pdsdata-dir=$pds_input_dir \
    --logfile=$logfile \
    |& tee export.out
