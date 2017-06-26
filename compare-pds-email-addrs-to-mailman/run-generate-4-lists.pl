#!/usr/bin/env perl

# Make 4 lists:

# 1. CSV of name,email_address of Active Members who are not on the
# listserve

# 2. CSV of name,email_address of Deceased Members who are on the
# listserve

# 3. CSV of name,email_address of Inactive (but not deceased) Members
# who are on the listserve

# 4. A list of all the other email addresses on the listserve (i.e.,
# we don't know who they are).

use strict;
use warnings;

use Data::Dumper;

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
        my ($addr, $name) = split(/\|/, $_);

	${$out}->{lc($addr)} = $name;
	++$count;
    }
    close(IN);
    print "Read $count addresses from $label\n";
}

# Read the sqlite: email addresses of active, non-deceased Members in
# $N database
my $sql = "SELECT MemEmail_DB.EMailAddress,Name
FROM Mem_DB
    INNER JOIN MemEmail_DB ON MemEmail_DB.MemRecNum = Mem_DB.MemRecNum
WHERE Mem_DB.deceased = 0 AND
    Mem_DB.PDSInactive$N = 0 AND
    (MemEmail_DB.FamEmail is NULL OR
     MemEmail_DB.FamEmail=0) AND
    Mem_DB.CensusMember$N = 1";

my $pds_active_members;
read_sql($sql, \$pds_active_members, "active members in PDS");

# Read the sqlite: email addresses of active Families in $N database
$sql = "SELECT MemEmail_DB.EmailAddress,Name
FROM Fam_DB
    INNER JOIN MemEmail_DB ON MemEmail_DB.MemRecNum = Fam_DB.FamRecNum
WHERE Fam_DB.PDSInactive$N = 0 AND
    (MemEmail_DB.FamEmail is NULL OR
     MemEmail_DB.FamEmail=1) AND
    Fam_DB.CensusFamily$N = 1";

my $pds_active_families;
read_sql($sql, \$pds_active_families, "active families in PDS");

# Merge the PDS active members and families into one unique set of
# addresses (because some Members and Families have the same email
# address(es))
my $pds_active;
foreach my $addr (keys(%{$pds_active_members})) {
    $pds_active->{$addr} = $pds_active_members->{$addr};
}
foreach my $addr (keys(%{$pds_active_families})) {
    $pds_active->{$addr} = $pds_active_families->{$addr};
}
my @pds_active_addrs = keys(%{$pds_active});
my $num_pds_active_addrs = $#pds_active_addrs + 1;
print "--> Total of $num_pds_active_addrs unique active member/family email addresses in PDS\n";

# Now search SQL for all deceased Members with email addresses in any
# database
$sql = "SELECT MemEmail_DB.EMailAddress,Name
FROM Mem_DB
    INNER JOIN MemEmail_DB ON MemEmail_DB.MemRecNum = Mem_DB.MemRecNum
WHERE Mem_DB.deceased = 1 AND
    (MemEmail_DB.FamEmail is NULL or MemEmail_DB.FamEmail = 0)";

my $pds_deceased;
read_sql($sql, \$pds_deceased, "deceased members in PDS");

# Now search SQL for all inactive (but not deceased) Members with
# email addresses in any database
$sql = "SELECT MemEmail_DB.EMailAddress,Name
FROM Mem_DB
    INNER JOIN MemEmail_DB ON MemEmail_DB.MemRecNum = Mem_DB.MemRecNum
WHERE Mem_DB.deceased = 0 AND
      (Mem_DB.PDSInactive1 = 1 OR
       Mem_DB.PDSInactive2 = 1 OR
       Mem_DB.PDSInactive3 = 1 OR
       Mem_DB.PDSInactive4 = 1 OR
       Mem_DB.PDSInactive4 = 1 OR
       Mem_DB.PDSInactive5 = 1) AND
     (MemEmail_DB.FamEmail is NULL or MemEmail_DB.FamEmail = 0)";

my $pds_inactive;
read_sql($sql, \$pds_inactive, "inactive-not-deceased members in PDS");

# We must search and prune from the mailman list in order:
# 1. Active in $N
# 2. Deceased in any
# 3. Inactive in any
# 4. All others

# Do the searches / pruning
my @mm_addrs = keys(%{$mailman});

# 1. Find those in the listserve who are active in $N
my $mm_active;
foreach my $addr (@mm_addrs) {
    if (exists($pds_active->{$addr})) {
        $mm_active->{$addr} = $pds_active->{$addr};
        delete($mailman->{$addr});
    }
}

# 2. Of the remaining in the listserve, find who are deceased in any
@mm_addrs = keys(%{$mailman});
my $mm_deceased;
foreach my $addr (@mm_addrs) {
    if (exists($pds_deceased->{$addr})) {
        $mm_deceased->{$addr} = $pds_deceased->{$addr};
        delete($mailman->{$addr});
    }
}

# 3. Of the remaining in the listserve, find who are inactive in any
@mm_addrs = keys(%{$mailman});
my $mm_inactive;
foreach my $addr (@mm_addrs) {
    if (exists($pds_inactive->{$addr})) {
        $mm_inactive->{$addr} = $pds_inactive->{$addr};
        delete($mailman->{$addr});
    }
}

# 4. Anyone remaining in the listserve is unknown
my $mm_unknown;
foreach my $addr (keys(%{$mailman})) {
    $mm_unknown->{$addr} = 1;
}

###############################################

# Now generate 3 CSVs and 1 list

# 1. From an "active members/families in the listserve" list,
# construct the "opposite" list: active members/families who are *not*
# in the listserve.  Then output that as a CSV.
my @pds_active_addrs = keys(%{$pds_active});
foreach my $addr (@pds_active_addrs) {
    if (exists($mm_active->{$addr})) {
        delete($pds_active->{$addr});
    }
}
my $file = "1-active-in-pds-not-in-listserve.csv";
unlink($file);
open(OUT, ">$file")
    || die "Can't write to $file";
print OUT "\"Email address\",\"Name\"\n";
for my $addr (sort(keys(%{$pds_active}))) {
    print OUT "\"$addr\",\"$pds_active->{$addr}\"\n";
}
close(OUT);

# 2. Output CSV of deceased members in the listserve
$file = "2-deceased-in-pds-but-still-in-listserve.csv";
unlink($file);
open(OUT, ">$file")
    || die "Can't write to $file";
print OUT "\"Email address\",\"Name\"\n";
for my $addr (sort(keys(%{$mm_deceased}))) {
    print OUT "\"$addr\",\"$mm_deceased->{$addr}\"\n";
}
close(OUT);

# 3. Output CSV of inactive-but-not-deceased members in the listserve
$file = "3-inactive-but-not-deceased-in-pds-but-still-in-listserve.csv";
unlink($file);
open(OUT, ">$file")
    || die "Can't write to $file";
print OUT "\"Email address\",\"Name\"\n";
for my $addr (sort(keys(%{$mm_inactive}))) {
    print OUT "\"$addr\",\"$mm_inactive->{$addr}\"\n";
}
close(OUT);

# 4. Output CSV of everyone else
$file = "4-everyone-else-in-listserve.csv";
unlink($file);
open(OUT, ">$file")
    || die "Can't write to $file";
print OUT "\"Email address\"\n";
for my $addr (sort(keys(%{$mm_unknown}))) {
    print OUT "\"$addr\"\n";
}
close(OUT);

exit(0);
