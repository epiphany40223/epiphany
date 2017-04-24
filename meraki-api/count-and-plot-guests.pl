#!/usr/bin/env perl

use strict;

use Data::Dumper;
use POSIX;
use DateTime;
use DBI;

my $sqlite_file;
# On WOPR / queeg
$sqlite_file = "/home/jeff/ecc-meraki-data/data.sqlite3";
if (! -f $sqlite_file) {
    # Jeff's laptop
    $sqlite_file = "/Users/jsquyres/git/epiphany/meraki-api/ecc-meraki-data/data.sqlite3";
}
if (! -f $sqlite_file) {
    die "Can't fine a datafile to open";
}

#######################################################################

my $local_time_zone = DateTime::TimeZone->new( name => 'local' );

# This calculates an offset of GMT from our local time.  This isn't
# 100% accurate on dates that change time (because they don't change
# time at midnight), but it's close enough for this app.  :-)
sub calc_gmt_offset {
    my $dt = shift;

    # The Meraki timestamps a reportedly in Zulu time (GMT), but
    # they're actually *not*.  They're in America/New York time.
    # Sigh.  So return an offset of 0.
    return 0;






    my $gmt_foo = DateTime->new(
	year       => $dt->year(),
	month      => $dt->month(),
	day        => $dt->day(),
	hour       => 12,
	minute     => 0,
	second     => 0,
	nanosecond => 0,
	time_zone  => 'GMT',
	);
    my $local_foo = DateTime->new(
	year       => $dt->year(),
	month      => $dt->month(),
	day        => $dt->day(),
	hour       => 12,
	minute     => 0,
	second     => 0,
	nanosecond => 0,
	time_zone  => $local_time_zone,
	);

    return ($gmt_foo->epoch() - $local_foo->epoch());
}

#######################################################################

my $dbh = DBI->connect("dbi:SQLite:dbname=$sqlite_file", undef, undef, {
#    sqlite_open_flags => SQLITE_OPEN_READONLY,
		       });
die "Can't open database"
    if (!$dbh);

my $sql_base  = "select distinct clientMac,ipv4,manufacturer from data where";
my $sql_next .= "ssid='Epiphany (pw=epiphany)' and ipv4 != '/0.0.0.0' and seenEpoch >= ? and seenEpoch < ? ";
my $sql_mac   = "$sql_base apMac = ? and $sql_next order by apMac";
my $sql_nomac = "$sql_base $sql_next";

my $sth_mac   = $dbh->prepare($sql_mac);
my $sth_nomac = $dbh->prepare($sql_nomac);

sub doit {
    my $apMac = shift;
    my $apName = shift;
    my $dt = shift;

    # Create a timestamp range that we want for this specific date,
    # and ensure to account for the GMT offset.
    my $offset = calc_gmt_offset($dt);
    my $ts_start = $dt->epoch() - $offset;
    my $ts_end = $ts_start + (24 * 60 * 60);

    my $count = 0;
    if ($apMac ne "") {
	$sth_mac->execute($apMac, $ts_start, $ts_end);
	while ($sth_mac->fetchrow_array()) {
	    ++$count;
	}
    } else {
	$sth_nomac->execute($ts_start, $ts_end);
	while ($sth_nomac->fetchrow_array()) {
	    ++$count;
	}
    }

    my $date_str = $dt->strftime("%Y-%m-%d-%a");
    print "=== $date_str $apName: $count guests\n";

    return $count;
}

#######################################################################

# This makes sqlite3 happy
close(STDIN);

# First date data was collected was 9/6/2016
# ...then there was a bug and we didn't collect data betwen 2016-09-09T01:49:09Z
# 2016-09-12T01:26:15Z.  :-(
# ...so start looking for data on 2016-09-12 US Eastern.
my $dt = DateTime->new(
    year       => 2016,
    month      => 9,
    day        => 12,
    hour       => 0,
    minute     => 0,
    second     => 0,
    nanosecond => 0,
    time_zone  => $local_time_zone,
    );

my $meraki_move = DateTime->new(
    year       => 2016,
    month      => 10,
    day        => 16,
    hour       => 0,
    minute     => 0,
    second     => 0,
    nanosecond => 0,
    time_zone  => $local_time_zone,
    );

# Collect results for each date and each location
my $results;
my $count = 0;
while ($dt->epoch() < time()) {
    my $date_str = $dt->strftime("%Y-%m-%d-%a");

    # From when we started collecting Meraki data, we had 2 Meraki
    # WAPs at these MAC addresses:
    if (DateTime->compare($dt, $meraki_move) <= 0) {
	$results->{$date_str}->{wc} =
	    doit("00:18:0a:79:a5:e2", "WC", $dt);
	$results->{$date_str}->{ehcr} =
	    doit("00:18:0a:79:8e:2d", "EH Copyroom", $dt);
	$results->{$date_str}->{all} =
	    doit("", "All", $dt);
    }
    # As of 2016-10-16, we installed several more Meraki APs and moved
    # the the WC AP to EH phone room.  For this script, just gather
    # stats for these APs:
    else {
	$results->{$date_str}->{wc} =
	    doit("e0:55:3d:91:a8:b0", "WC", $dt);
	$results->{$date_str}->{cc} =
	    doit("e0:55:3d:92:84:a0", "CC", $dt);
	$results->{$date_str}->{ehcr} =
	    doit("00:18:0a:79:8e:2d", "EH Copyroom", $dt);
	$results->{$date_str}->{all} =
	    doit("", "All", $dt);
    }

    my $e = $dt->epoch() + (24 * 60 * 60);
    $dt = DateTime->from_epoch(epoch => $e);
    ++$count;
}

#######################################################################

# Save the raw data
my $file;
$file = "results.dump";
unlink($file);
open(OUT, ">$file")
    || die "Can't write to $file";
print OUT Dumper($results);
close(OUT);

# Remove the old data file, write a new one
$file = "results.txt";
unlink($file);
open(OUT, ">$file")
    || die "Can't write to $file";

# Grab all the dates and locations
my @dates = sort(keys(%{$results}));
my @locations = sort(keys(%{$results->{$dates[$count - 1]}}));

# Write all the data
my $num = 1;
foreach my $date (@dates) {
    print OUT "$date $num ";
    foreach my $location (@locations) {
	if (exists($results->{$date}->{$location})) {
	    print OUT "$results->{$date}->{$location} ";
	} else {
	    print OUT "0 ";
	}
    }
    print OUT "\n";
    ++$num;
}
close(OUT);

#######################################################################

# Gnuplot it!
# Make a string with the gnuplot commands
# Use the dates as xtics
my $gp;
$gp = 'set terminal pdf
set title "Guests on ECC Meraki AP wifi networks"
set grid
set xlabel "Date"
set ylabel "Number of guests"
set key top left

set xtics border in scale 1,0.5 nomirror rotate by -45 autojustify
set xtics (';
# Write out the dates for each X tic label
my $num = 1;
my $count = 0;
foreach my $date (@dates) {
    # Is this a major (0) or minor (1) tic?
    my $level = 1;
    if ($count % 7 == 0) {
	$level = 0;
    }
    ++$count;

    $gp .= "\"$date\" $num $level";
    $gp .= ", "
	if ($num <= $#dates);
    ++$num;
}
$gp .= ')

set output "ecc-meraki-data.pdf";
plot ';

# Plot each AP
my $column = 3;
foreach my $location (@locations) {
    $gp .= "\"$file\" using 2:$column with lines title \"$location\",";
    ++$column;
}

$gp .= "
quit\n";

# Do the actual plot
open(GP, "|gnuplot") || die "Can't open gnuplot";
print $gp;
print GP $gp;
close(GP);

# All done!
exit(0);
