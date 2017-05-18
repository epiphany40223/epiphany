#!/usr/bin/env perl

use strict;
use warnings;

use Getopt::Long;
use Time::HiRes;

my ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = localtime(time);

my $sqlite3_bin = "sqlite3";
my $pxview_bin = "pxview";
my $data_dir;
my $database_name = sprintf("pdschurchoffice-%04d-%02d-%02d-%02d%02d%02d.sqlite3",
                            $year + 1900, $mon + 1, $mday,
                            $hour, $min, $sec);

my $help_arg = 0;
my $debug_arg = 0;

###############################################################################

&Getopt::Long::Configure("bundling");
my $ok = Getopt::Long::GetOptions("sqlite3=s" => \$sqlite3_bin,
                                  "sqlite3-db-name=s", \$database_name,
                                  "pxview=s" => \$pxview_bin,
                                  "pdsdata-dir=s" => \$data_dir,
                                  "debug" => \$debug_arg,
                                  "help|h" => \$help_arg);
if (!$ok || $help_arg) {
    print "$0 [--sqlite3=SQLITE3_BIN] [--pxview=PXVIEW_BIN] [--pdsdata-dir=DIR][--sqlite3-db-name=NAME]\n";
    exit($ok);
}

###############################################################################

sub find {
    my $bin_name = shift;
    my $arg_value = shift;

    if (defined($arg_value)) {
        if ($arg_value =~ /^\// && -x $arg_value) {
            return $arg_value;
        } elsif ($arg_value =~ /^\./ && -x $arg_value) {
            return $arg_value;
        } else {
            $bin_name = $arg_value;
        }
    }

    foreach my $dir (split(/:/, $ENV{PATH})) {
        my $b = "$dir/$bin_name";
        return $b
            if (-x $b);
    }

    return undef;
}

$pxview_bin = find("pxview", $pxview_bin)
    if (!defined($pxview_bin));
$sqlite3_bin = find("sqlite3", $sqlite3_bin)
    if (!defined($sqlite3_bin));
die "Can't fix pxview executable: $pxview_bin"
    if (!defined($pxview_bin));
die "Can't find sqlite3 executable"
    if (!defined($sqlite3_bin));
die "Must specify PDS data dir"
    if (!defined($data_dir));
die "Can't find PDS data dir: $data_dir"
    if (! -d $data_dir);

###############################################################################

unlink($database_name);

###############################################################################

opendir(my $dh, $data_dir) ||
    die "Can't open $data_dir";
print "PDS data dir: $data_dir\n"
    if ($debug_arg);
my @dbs = grep { /\.DB$/ && -f "$data_dir/$_" } readdir($dh);
closedir($dh);

###############################################################################

my $echo = "";
$echo = "-echo "
    if ($debug_arg);
open(SQLITE, "|$sqlite3_bin $echo$database_name") ||
    die "Can't run sqlite3 binary: $sqlite3_bin";

# This helps SQLite performance considerably (it's slightly risky, in
# general, because it removes some atomic-ness of transactions, but
# for this application, it's fine).
print SQLITE "PRAGMA $database_name.synchronous=0;\n";

foreach my $db (@dbs) {
    print "=== PDS table: $db\n";

    my $start_time = Time::HiRes::time();
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

    # We dont' currently care about the *GIANT* databases (that take
    # -- literally -- hours to import on an RPi).
    if ($db =~ /fund/i) {
        print "   ==> Skipping giant table $db\n";
        next;
    }

    # Yes, we use "--sql" here, not "--sqlite".  See the comment below
    # for the reason why.  :-(
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

    open(SQL, $sql_file) ||
        die "Can't open $sql_file";
    my $transaction_started = 0;
    while (<SQL>) {
        my $str = $_;

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

        # If we're insertting and we haven't started the transaction,
        # start the transaction.
        if (!$transaction_started && $str =~ /^insert/i) {
            print SQLITE "BEGIN TRANSACTION;\n";
            $transaction_started = 1;
        }
        print SQLITE $str;
    }
    close(SQL);
    print SQLITE ";\n";
    print SQLITE "END TRANSACTION;\n"
        if ($transaction_started);

    my $stop_time = Time::HiRes::time();
    my $elapsed = $stop_time - $start_time;
    printf("    Elapsed time for %s table: %0.02f\n", $db, $elapsed);
    #unlink($sql_file);
}

close(SQLITE);

print "**** All done!\n";

exit(0);
