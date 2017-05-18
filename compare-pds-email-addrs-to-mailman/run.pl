#!/usr/bin/env perl

use strict;
use warnings;

# Read the mailman list
my $mailman;
open(IN, "parishioner.txt")
    || die "Can't open parishioner.txt";
my $count = 0;
while (<IN>) {
    chomp;
    $mailman->{lc($_)} = 1;
    ++$count;
}
close(IN);
print "Read $count addresses in parishioner.txt\n";

# Read the sqlite
my $sql = "SELECT MemEmail_DB.EMailAddress FROM Mem_DB INNER JOIN MemEmail_DB ON MemEmail_DB.MemRecNum = Mem_DB.MemRecNum WHERE  Mem_DB.deceased = 0 AND Mem_DB.PDSInactive1 = 0 AND Mem_DB.PDSInactive2 = 0 AND Mem_DB.PDSInactive3 = 0 AND Mem_DB.PDSInactive4 = 0 AND Mem_DB.PDSInactive5 = 0 AND MemEmail_DB.EmailOverMail = 1 AND (MemEmail_DB.FamEmail is NULL or MemEmail_DB.FamEmail=0)";

my $pds;
open(IN, "sqlite3 pdsdata.sqlite3 \"$sql\"|")
    || die "Can't run sqlite";
$count = 0;
while (<IN>) {
    chomp;
    $pds->{lc($_)} = 1;
    ++$count;
}
close(IN);
print "Read $count addresses from members in PDS\n";

$sql = "SELECT MemEmail_DB.EmailAddress FROM Fam_DB INNER JOIN MemEmail_DB ON MemEmail_DB.MemRecNum = Fam_DB.FamRecNum WHERE  Fam_DB.PDSInactive1 = 0 AND Fam_DB.PDSInactive2 = 0 AND Fam_DB.PDSInactive3 = 0 AND Fam_DB.PDSInactive4 = 0 AND Fam_DB.PDSInactive5 = 0 AND MemEmail_DB.EmailOverMail = 1 AND (MemEmail_DB.FamEmail is NULL or MemEmail_DB.FamEmail=1)";

open(IN, "sqlite3 pdsdata.sqlite3 \"$sql\"|")
    || die "Can't run sqlite";
$count = 0;
while (<IN>) {
    chomp;
    $pds->{lc($_)} = 1;
    ++$count;
}
close(IN);
print "Read $count addresses from families in PDS\n";

my $unique;
my $in_both;
my $only_in_mailman;
my $only_in_pds;

foreach my $mailman_addr (sort(keys(%{$mailman}))) {
    $unique->{$mailman_addr} = 1;
    if (exists($pds->{$mailman_addr})) {
        $in_both->{$mailman_addr} = 1;
    } else {
        $only_in_mailman->{$mailman_addr} = 1;
    }
}

foreach my $pds_addr (sort(keys(%{$pds}))) {
    $unique->{$pds_addr} = 1;
    if (exists($mailman->{$pds_addr})) {
        $in_both->{$pds_addr} = 1;
    } else {
        $only_in_pds->{$pds_addr} = 1;
    }
}

my @unique_keys = keys(%{$unique});
my @in_both_keys = keys(%{$in_both});
my @only_in_mailman_keys = keys(%{$only_in_mailman});
my @only_in_pds_keys = keys(%{$only_in_pds});

print "Total unique email addresses: " . ($#unique_keys + 1) . "\n";
print "In both: " . ($#in_both_keys + 1) . "\n";
print "Only in mailman: " . ($#only_in_mailman_keys + 1) . "\n";
print "Only in pds: " . ($#only_in_pds_keys + 1) . "\n";
