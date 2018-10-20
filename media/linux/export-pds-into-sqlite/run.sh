#!/bin/zsh

set -x

pds_input_dir=/media/sf_pdschurch/Data

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

# If this is the first run after midnight, save a copy for archival
# purposes.
t=`date '+%H%M'`
yes=`expr $t \< 5`
if test $yes -eq 1; then
    d=`date '+%Y-%m-%d'`
    cp $sqlite_out_dir/pdschurch.sqlite3 \
	$sqlite_out_dir/archives/$d-pdschurch.sqlite3

    # Also make a full backup of the actual data files, too
    date
    echo "Copying all PDS data files for a backup..."
    outdir="$sqlite_out_dir/archives/$d-pds-raw-data"
    mkdir -p "$outdir"
    cp -r "$pds_input_dir" "$outdir"

    date
    echo "Tarring up PDS data files for backup..."
    cd "$outdir"
    cd ..
    p=`pwd`
    b=`basename $outdir`
    tar jcvf "$p/$b.tar.bz2" "$b"
    rm -rf "$b"

    date
    echo "Done with PDS files backup"
fi
