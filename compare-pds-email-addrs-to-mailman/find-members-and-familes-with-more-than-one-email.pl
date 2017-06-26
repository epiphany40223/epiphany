#!/usr/bin/env perl

use strict;
use warnings;

use DBI;
use Data::Dumper;

my $N = 1;

my $sqlite_file = "/Users/jsquyres/git/epiphany/compare-pds-email-addrs-to-mailman/pdsdata.sqlite3";
die "Can't fine a datafile to open"
    if (! -r $sqlite_file);

my $dbh = DBI->connect("dbi:SQLite:dbname=$sqlite_file", undef, undef, {
    #    sqlite_open_flags => SQLITE_OPEN_READONLY,
		       });
die "Can't open database"
    if (!$dbh);

##############################################################

doit("Families");
doit("Members");

sub doit {
    my $label = shift;

    # First, find all the unique MemRecNums, with either ACTIVE
    # families or ACTIVE members
    my $sql;
    if ($label eq "Families") {
	$sql = "SELECT DISTINCT(Fam_DB.FamRecNum) FROM Fam_DB ";
	$sql .= "INNER JOIN MemEMail_DB ON MemEMail_Db.MemRecNum = Fam_DB.FamRecNum ";
	$sql .= "WHERE famemail=1 AND " .
	    "(Fam_DB.PDSInactive$N = 0 OR Fam_Db.PDSInactive$N is null) AND " .
	    "Fam_DB.CensusFamily$N = 1";
    } else {
	$sql = "SELECT DISTINCT(Mem_DB.MemRecNum) FROM Mem_DB ";
	$sql .= "INNER JOIN MemEmail_DB ON MemEmail_DB.MemRecNum = Mem_DB.MemRecNum ";
	$sql .= "WHERE (famemail=0 or famemail is null) AND " .
	    "Mem_DB.deceased = 0 AND " .
	    "(Mem_DB.PDSInactive$N = 0 OR Mem_DB.PDSInactive$N is null) AND " .
	    "Mem_DB.CensusMember$N = 1";
    }
    print "SQL: $sql\n";
    my $sth = $dbh->prepare($sql);
    $sth->execute()
	|| die $DBI::errstr;

    my @recnums;
    while (my @row = $sth->fetchrow_array()) {
	push(@recnums, $row[0]);
    }

    my $count = $#recnums + 1;
    my $results;
    print "$label: found $count unique addresses\n";
    foreach my $recnum (@recnums) {
	$sql = "select count(emailrec) from mememail_db where memrecnum=$recnum";
	$sth = $dbh->prepare($sql);
	$sth->execute()
	    || die $DBI::errstr;
	my @row = $sth->fetchrow_array();
	if (exists($results->{$row[0]})) {
	    $results->{$row[0]}++;
	} else {
	    $results->{$row[0]} = 1;
	}
    }
    print "$label: final results:\n";
    print Dumper($results);
}
