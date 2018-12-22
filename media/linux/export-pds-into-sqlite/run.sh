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
    # Upload some files to a Google drive
    archive_dir="`readlink -f $sqlite_out_dir/archives`"
    uploader_dir="`readlink -f ../google-drive-uploader`"
    script=`readlink -f $uploader_dir/google-drive-uploader.py`
    client_id=`readlink -f $uploader_dir/google-uploader-client-id.json`
    user_credentials=`readlink -f $uploader_dir/google-uploader-user-credentials.json`
    dest_folder="0ANbM4b6o0km8Uk9PVA"

    # Upload the latest sqlite file to Google, but rename it with
    # today's date first.
    d=`date '+%Y-%m-%d'`
    cp "$sqlite_out_dir/pdschurch.sqlite3" \
       "$archive_dir/$d-pdschurch.sqlite3"
    $script \
        --app-id $client_id \
        --user-credentials $user_credentials \
        --dest $dest_folder \
	"$archive_dir/$d-pdschurch.sqlite3"
    rm -f "$archive_dir/$d-pdschurch.sqlite3"

    # Now make a full backup of the PDS data files in a directory with
    # today's date in it.
    date
    echo "Copying all PDS data files for a backup..."
    outdir="$archive_dir/$d-pds-raw-data"
    mkdir -p "$outdir"
    cp -r "$pds_input_dir" "$outdir"

    date
    echo "Tarring up PDS data files for backup..."
    cd "$archive_dir"
    b="`basename $outdir`"
    tar jcf "$b.tar.bz2" "$b"
    rm -rf "$b"

    # Now upload that tarfile to a Google Team Drive
    cd "$uploader_dir"
    $script \
        --app-id $client_id \
        --user-credentials $user_credentials \
        --dest $dest_folder \
        "$archive_dir/$b.tar.bz2"

    # Once it's uploaded, delete the local copy
    rm -f "$archive_dir/$b.tar.bz2"

    date
    echo "Done with PDS files backup"
fi
