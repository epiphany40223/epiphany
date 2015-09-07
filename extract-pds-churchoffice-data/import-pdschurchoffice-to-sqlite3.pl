#!/usr/bin/env perl

use strict;
use warnings;

use Getopt::Long;

my $sqlite3_bin = "sqlite3";
my $pxview_bin = "pxview";
my $data_dir = ".";
my $database_name = "pdschurchoffice";

my $help_arg = 0;
my $debug_arg = 0;

###############################################################################

&Getopt::Long::Configure("bundling");
my $ok = Getopt::Long::GetOptions("sqlite3=s" => \$sqlite3_bin,
                                  "pxview=s" => \$pxview_bin,
                                  "data-dir=s" => \$data_dir,
                                  "database-name=s", \$database_name,
                                  "debug" => \$debug_arg,
                                  "help|h" => \$help_arg);
if (!$ok || $help_arg) {
    print "$0 [--sqlite3=SQLITE3_BIN] [--pxview=PXVIEW_BIN] [--data-dir=DIR]\n";
    exit(0);
}

###############################################################################

die "Can't fix pxview executable: $pxview_bin"
    if (! -x $pxview_bin);
die "Can't find data dir: $data_dir"
    if (! -d $data_dir);

###############################################################################

unlink($database_name);

###############################################################################

opendir(my $dh, $data_dir) ||
    die "Can't open $data_dir";
my @dbs = grep { /\.DB$/ && -f "$data_dir/$_" } readdir($dh);
closedir($dh);

###############################################################################

my $echo = "";
$echo = "-echo "
    if ($debug_arg);
open(SQLITE, "|$sqlite3_bin $echo$database_name") ||
    die "Can't run sqlite3 binary: $sqlite3_bin";

print SQLITE "PRAGMA $database_name.synchronous=0;\n";

foreach my $db (@dbs) {
    print "=== PDS table: $db\n";

    my $table_base = $db;
    $table_base =~ s/\.DB$//;

    # PDS has "PDS" and "PDS[digit]" tables.  "PDS" is the real one;
    # skip "PDS[digit]" tables.  Sigh.  Ditto for RE, SCH.
    if ($db =~ /^PDS\d+.DB$/i ||
        $db =~ /^RE\d+.DB$/i ||
        $db =~ /^SCH\d+.DB$/i) {
        print "    ==> Skipping bogus $db table\n";
        next;
    }
    # PDS also has a duplicate table "resttemp_db" in the AskRecNum
    # and RecNum databases.  They appear to be empty, so just skip
    # them.
    if ($db =~ /^AskRecNum.DB/i ||
        $db =~ /^RecNum.DB/i) {
        print "    ==> Skipping bogus $db table\n";
        next;
    }

    my $cmd = "$pxview_bin --sql $data_dir/$db";

    my $mb = $db;
    $mb =~ s/\.DB//;
    $mb = "$data_dir/$mb.MB";
    $cmd .= " --blobfile=$mb"
        if (-r $mb);

    # Sadly, we can't have pxview write directly to the sqlite
    # database because PDS has some field names that are SQL reserved
    # words.  :-( Hence, we have to have pxview output the SQL, we
    # then twonk the SQL a bit, and then we can import it into
    # the sqlite3 database using the sqlite3 executable.
    my $sql_file = "$data_dir/$table_base.sql";
    unlink($sql_file);
    $cmd .= " -o $sql_file 2>/dev/null";

    print "=== PXVIEW command: $cmd\n"
        if ($debug_arg);
    system($cmd);

    # SQLite3 (greatly) benefits by surrounding all the INSERT lines
    # with BEGIN.. (especially databases like FundHist, which have
    # zillions of INSERT lines).
    my $found_first_insert = 0;

    open(SQL, $sql_file) ||
        die "Can't open $sql_file";
    while (<SQL>) {
        my $str = $_;

        if (!$found_first_insert && $str =~ /INSERT/) {
            $str =~ s/INSERT/BEGIN;\nINSERT/;
            $found_first_insert = 1;
        }

        # PDS uses some fields named "order", "key", "default", etc.,
        # which are keywords in SQL
        $str =~ s/\border\b/pdsorder/i;
        $str =~ s/\bkey\b/pdskey/i;
        $str =~ s/\bdefault\b/pdsdefault/i;
        $str =~ s/\bcheck\b/pdscheck/i;
        $str =~ s/\bboth\b/pdsboth/i;
        $str =~ s/\bowner\b/pdsowner/i;
        $str =~ s/\baccess\b/pdsaccess/i;
        $str =~ s/\bsql\b/pdssql/i;

        # SQLite does not have a boolean class; so turn TRUE and FALSE
        # into 1 and 0.
        $str =~ s/TRUE/1/g;
        $str =~ s/FALSE/0/g;

        print "SQL: $str"
            if ($debug_arg);
        print SQLITE $str;
    }
    close(SQL);
    print SQLITE ";COMMIT"
        if ($found_first_insert);
    print SQLITE ";\n";
    #unlink($sql_file);
    #sleep(1);
}

close(SQLITE);

print "**** All done!\n";

exit(0);
