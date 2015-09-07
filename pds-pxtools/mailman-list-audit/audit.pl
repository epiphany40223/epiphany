#!/usr/bin/env perl

use strict;
use warnings;

use Getopt::Long;
use Data::Dumper;

my $sqlite3_bin = "sqlite3";
my $database = "pdschurchoffice.sqlite3";
my $addresses;
my $keyword;

my $debug_arg;
my $help_arg;

###############################################################################

&Getopt::Long::Configure("bundling");
my $ok = Getopt::Long::GetOptions("sqlite3=s" => \$sqlite3_bin,
                                  "database=s", \$database,
                                  "addresses=s", \$addresses,
                                  "keyword=s", \$keyword,
                                  "debug" => \$debug_arg,
                                  "help|h" => \$help_arg);
if (!$ok || $help_arg) {
    print "$0 [--sqlite3=SQLITE3_BIN] --database=DB --addresses=FILE --keyword=KEYWORD\n";
    exit(0);
}

###############################################################################

die "Can't find sqlite3 database $database"
    if (!defined($database) || ! -r $database);
die "Can't find mailman address filename $addresses"
    if (!defined($addresses) || ! -r $addresses);
die "Must specify a keyword"
    if (!defined($keyword));

###############################################################################

# Read in the list of addresses

open(MA, $addresses) ||
    die "Can't open $addresses";
my @addrs;
while (<MA>) {
    chomp;
    push(@addrs, $_);
}
close(MA);

###############################################################################

sub do_sql {
    my $sql = shift;
    my @field_names = @_;

    print "=== SQL: $sql\n"
        if ($debug_arg);

    my $results = `$sqlite3_bin $database "$sql"`;

    if (defined($results)) {
        my @ret;
        foreach my $line (split(/\n/, $results)) {
            chomp($line);
            print "=== SQL RESULT: $line\n"
                if ($debug_arg);

            my @vals = split(/\|/, $line);
            my $record;
            my $i = 0;
            foreach my $field (@field_names) {
                $record->{$field} = $vals[$i];
                ++$i;
            }
            push(@ret, $record);
        }

        return @ret;
    }
}

# Look for the keyword in the list of keywords

my $sql;
$sql = "SELECT MemKWType_DB.DescRec FROM MemKWType_DB WHERE description='$keyword' COLLATE NOCASE";
my @results = do_sql($sql, qw/descrec/);

die "Cannot find keyword in database: $keyword"
    if ($#results < 0);
die "Keyword found multiple times: $keyword"
    if ($#results > 0);

my $keyword_descrec = $results[0]->{descrec};
print "=== Got ID for keyword '$keyword': $keyword_descrec\n";

###############################################################################

# Look up each mailman address in the database.  It will either be:
#
# 1. Already marked with the keyword
# 2. Not already marked with the keyword
# 3. Not found in the database

my @keyword_set;
my @keyword_notset;
my @notfound;

foreach my $addr (@addrs) {
    print "=== Checking addr: $addr\n"
        if ($debug_arg);

    $sql = "SELECT Mem_DB.MemRecNum, Mem_DB.Name, MemEmail_DB.EMailAddress FROM Mem_DB INNER JOIN MemEmail_DB ON MemEmail_DB.MemRecNum = Mem_DB.MemRecNum WHERE MemEmail_DB.EmailAddress = '$addr' COLLATE NOCASE";
    @results = do_sql($sql, qw/memrecnum name email/);

    if ($#results < 0) {
        push(@notfound, $addr);
    } else {
        foreach my $result (@results) {
            my $to_save = {
                name => $result->{name},
                email => $result->{email}
            };

            $sql = "SELECT MemKW_DB.MemRecNum FROM MemKW_DB WHERE MemKW_DB.MemRecNum=$result->{memrecnum} AND MemKW_DB.DescRec=$keyword_descrec";
            my @r = do_sql($sql);
            if ($#r >= 0) {
                push(@keyword_set, $to_save);
            } else {
                push(@keyword_notset, $to_save);
            }
        }
    }
}

###############################################################################

print "
Members found with keyword set:\n";
print Dumper(@keyword_set);

print "
Members found WITHOUT keyword set:\n";
print Dumper(@keyword_notset);

print "
Email addresses not found in PDS:\n";
print Dumper(@notfound);
