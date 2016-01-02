#!/usr/bin/env perl

use strict;
use warnings;

use Getopt::Long;

my ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = localtime(time);

my $mysql_user;
my $mysql_password;
my $mysql_bin = "mysql";
my $pxview_bin = "pxview";
my $data_dir = ".";
my $database_name = sprintf("pdschurchoffice-%04d-%02d-%02d-%02d%02d%02d",
                            $year + 1900, $mon + 1, $mday,
                            $hour, $min, $sec);

my $help_arg = 0;
my $debug_arg = 0;

###############################################################################

&Getopt::Long::Configure("bundling");
my $ok = Getopt::Long::GetOptions("user=s" => \$mysql_user,
                                  "password=s" => \$mysql_password,
                                  "mysql=s" => \$mysql_bin,
                                  "pxview=s" => \$pxview_bin,
                                  "data-dir=s" => \$data_dir,
                                  "database-name=s", \$database_name,
                                  "debug" => \$debug_arg,
                                  "help|h" => \$help_arg);
if (!$ok || $help_arg) {
    print "$0 --user=MYSQL_USER --password=MYSQL_PASSWORD [--mysql=MYSQL_BIN] [--pxview=PXVIEW_BIN] [--data-dir=DIR]\n";
    exit(0);
}

die "Must specify --user and --password"
    if (!defined($mysql_user) || !defined($mysql_password));

###############################################################################

die "Can't find mysql executable: $mysql_bin"
    if (! -x $mysql_bin);
die "Can't fix pxview executable: $pxview_bin"
    if (! -x $pxview_bin);
die "Can't find data dir: $data_dir"
    if (! -d $data_dir);

###############################################################################

open(M, "|$mysql_bin --user=$mysql_user --password=$mysql_password") ||
    die "Can't open mysql";
print M "drop database $database_name;
create database $database_name;
use $database_name;\n";

###############################################################################

opendir(my $dh, $data_dir) ||
    die "Can't open $data_dir";
my @dbs = grep { /\.DB$/ && -f "$data_dir/$_" } readdir($dh);
closedir($dh);

###############################################################################

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

    my $sql_file = "$data_dir/$table_base.sql";
    unlink($sql_file);
    $cmd .= " -o $sql_file 2>/dev/null";

    print "=== PXVIEW command: $cmd\n"
        if ($debug_arg);
    system($cmd);

    open(SQL, $sql_file) ||
        die "Can't open $sql_file";
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
        print "SQL: $str"
            if ($debug_arg);
        print M $str;
    }
    close(SQL);
    print M ";\n";
    #unlink($sql_file);
}

print M "quit\n";
close(M);

print "**** All done!\n";

exit(0);
