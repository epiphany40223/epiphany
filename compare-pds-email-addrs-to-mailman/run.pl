#!/usr/bin/env perl

use strict;
use warnings;

my $N = 1;

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

#------------------------------------------------------------------

sub read_sql {
    my $sql = shift;
    my $out = shift;
    my $label = shift;

    open(IN, "sqlite3 pdsdata.sqlite3 \"$sql\"|")
	|| die "Can't run sqlite";
    $count = 0;
    while (<IN>) {
	chomp;
	${$out}->{lc($_)} = 1;
	++$count;
    }
    close(IN);
    print "Read $count addresses from $label\n";
}

# Read the sqlite: email addresses of active, non-deceased Members
my $sql = "SELECT MemEmail_DB.EMailAddress FROM Mem_DB INNER JOIN MemEmail_DB ON MemEmail_DB.MemRecNum = Mem_DB.MemRecNum WHERE  Mem_DB.deceased = 0 AND Mem_DB.PDSInactive$N = 0 AND (MemEmail_DB.FamEmail is NULL or MemEmail_DB.FamEmail=0) AND Mem_DB.CensusMember$N = 1";

my $pds;
read_sql($sql, \$pds, "active members in PDS");

# Read the sqlite: email addresses of active Families
$sql = "SELECT MemEmail_DB.EmailAddress FROM Fam_DB INNER JOIN MemEmail_DB ON MemEmail_DB.MemRecNum = Fam_DB.FamRecNum WHERE  Fam_DB.PDSInactive$N = 0 AND (MemEmail_DB.FamEmail is NULL or MemEmail_DB.FamEmail=1) AND Fam_DB.CensusFamily$N = 1";

read_sql($sql, \$pds, "active families in PDS");

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

# Find how many of the mailman addresses that are not active in
# database $N are in PDS somewhere (e.g., inactive in any $N
# database).

# First, take all the mailman addresses and subtract off
# active+non-deceased $N Member addresses and active $N Family
# addresses.
my $mm_copy;
%{$mm_copy} = %{$mailman};
foreach my $addr (keys(%{$pds})) {
    delete $mm_copy->{$addr}
	if (exists($mm_copy->{$addr}));
}

#------------------------------------------------------------------

# Now search SQL for all inactive/deceased Members for any value of N.
$sql = "SELECT MemEmail_DB.EMailAddress
FROM Mem_DB
    INNER JOIN MemEmail_DB ON MemEmail_DB.MemRecNum = Mem_DB.MemRecNum
WHERE (Mem_DB.deceased = 1 OR
       Mem_DB.PDSInactive1 = 1 OR
       Mem_DB.PDSInactive2 = 1 OR
       Mem_DB.PDSInactive3 = 1 OR
       Mem_DB.PDSInactive4 = 1 OR
       Mem_DB.PDSInactive4 = 1 OR
       Mem_DB.PDSInactive5 = 1) AND
     (MemEmail_DB.FamEmail is NULL or MemEmail_DB.FamEmail = 0)";

my $found_inactive_mems;
read_sql($sql, \$found_inactive_mems, "inactive members with email addresses in any \$N");
foreach my $addr (keys(%{$found_inactive_mems})) {
    $mm_copy->{$addr} = 2
	if (exists($mm_copy->{$addr}));
}

# Now search SQL for all inactive Families for any value of N.
$sql = "SELECT MemEmail_DB.EmailAddress FROM Fam_DB INNER JOIN MemEmail_DB ON MemEmail_DB.MemRecNum = Fam_DB.FamRecNum WHERE (Fam_DB.PDSInactive1 = 1 OR Fam_DB.PDSInactive2 = 1 OR Fam_DB.PDSInactive3 = 1 OR Fam_DB.PDSInactive4 = 1 OR Fam_DB.PDSInactive5 = 1) AND (MemEmail_DB.FamEmail is NULL or MemEmail_DB.FamEmail=1)";

my $found_inactive_fams;
read_sql($sql, \$found_inactive_fams, "inactive families in any \$N");
foreach my $addr (keys(%{$found_inactive_fams})) {
    $mm_copy->{$addr} = 2
	if (exists($mm_copy->{$addr}));
}

my $ided_as_inactive = 0;
foreach my $addr (keys(%{$mm_copy})) {
    ++$ided_as_inactive
	if ($mm_copy->{$addr} == 2);
}

print "Found $ided_as_inactive addresses in mailman that are marked as inactive members or families in PDS\n";

#------------------------------------------------------------------

my @unique_keys = keys(%{$unique});
my @in_both_keys = keys(%{$in_both});
my @only_in_mailman_keys = keys(%{$only_in_mailman});
my @only_in_pds_keys = keys(%{$only_in_pds});
my @in_pds_keys = keys(%{$pds});
my @in_mailman_keys = keys(%{$mailman});

print "Total unique email addresses: " . ($#unique_keys + 1) . "\n";
print "Unique addresses in mailman: " . ($#in_mailman_keys + 1) . "\n";
print "Unique Member and Family email addresses in PDS: " . ($#in_pds_keys + 1) . "\n";
print "In both: " . ($#in_both_keys + 1) . "\n";
print "Only in mailman: " . ($#only_in_mailman_keys + 1) . "\n";
print "Only in pds: " . ($#only_in_pds_keys + 1) . "\n";
