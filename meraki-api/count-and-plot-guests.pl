#!/usr/bin/env perl

use strict;

use POSIX;
use DateTime;

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

sub doit {
    my $apMac = shift;
    my $apName = shift;
    my $dt = shift;

    my $date_str = $dt->strftime("%Y-%m-%d");
    print "=== For $apName on $date_str\n";

    my $file = "bogus.sql";
    open(TMP, ">$file")
        || die "Can't write to $file";

    my $sql = "select distinct clientMac,ipv4,manufacturer from data where ";
    $sql .=  "apMac = '$apMac' and "
        if ($apMac ne "");

    # Create a timestamp range that we want for this specific date,
    # and ensure to account for the GMT offset.
    my $offset = calc_gmt_offset($dt);
    my $ts_start = $dt->epoch() - $offset;
    my $ts_end = $ts_start + (24 * 60 * 60);

    $sql .= "ssid='Epiphany (pw=epiphany)' and ipv4 != '/0.0.0.0' and seenEpoch >= $ts_start and seenEpoch < $ts_end ";
    $sql .= "order by apMac"
        if ($apMac ne "");
    $sql .= ";";

    print "SQL: $sql\n";
    print TMP "$sql\n";
    close(TMP);

    open(SQL, "sqlite3 $sqlite_file -init $file|")
        || die "Can't run SQL";

    my $count = 0;
    while (<SQL>) {
        print $_;
        ++$count;
    }
    close(SQL);
    print "=== Total of $count rows\n";

    unlink($file);

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

# Collect results for each date and each location
my $results;
while ($dt->epoch() < time()) {
    my $date_str = $dt->strftime("%Y-%m-%d-%a");

    $results->{$date_str}->{wc} =
        doit("00:18:0a:79:a5:e2", "WC", $dt);
    $results->{$date_str}->{eh} =
        doit("00:18:0a:79:8e:2d", "EH Copyroom", $dt);
    $results->{$date_str}->{both} =
        doit("", "Both", $dt);

    my $e = $dt->epoch() + (24 * 60 * 60);
    $dt = DateTime->from_epoch(epoch => $e);
}

#######################################################################

# Remove the old data file, write a new one
my $file = "results.txt";
unlink($file);
open(OUT, ">$file")
    || die "Can't write to $file";

# Grab all the dates and locations
my @dates = sort(keys(%{$results}));
my @locations = sort(keys(%{$results->{$dates[0]}}));

# Write all the data
my $num = 1;
foreach my $date (@dates) {
    print OUT "$date $num ";
    foreach my $location (@locations) {
        print OUT "$results->{$date}->{$location} ";
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
set key bottom left

set xtics border in scale 1,0.5 nomirror rotate by -45  autojustify
set xtics (';
# Write out the dates for each X tic label
my $num = 1;
foreach my $date (@dates) {
    $gp .= "\"$date\" $num";
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
    $gp .= "\"$file\" using 2:$column with linespoints title \"$location\",";
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
