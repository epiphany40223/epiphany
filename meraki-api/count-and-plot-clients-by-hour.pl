#!/usr/bin/env perl

use strict;

use POSIX;
use DateTime;
use Getopt::Long;
use Data::Dumper;

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

sub doit_hour {
    my $apMac = shift;
    my $apName = shift;
    my $dt = shift;

    print "=== Searching for hour " . $dt->hour() . "\n";
    my $sql = "select distinct clientMac,ipv4 from data where ";
    $sql .=  "apMac = '$apMac' and "
	if ($apMac ne "");

    # Create a timestamp range that we want for this specific date,
    # and ensure to account for the GMT offset.
    my $offset = calc_gmt_offset($dt);
    my $ts_start = $dt->epoch() - $offset;
    my $ts_end = $ts_start + (60 * 60);

    # Limit it to a specific SSID or not
    #$sql .= "ssid='Epiphany (pw=epiphany)' and ipv4 != '/0.0.0.0' and ipv4 != '' and seenEpoch >= $ts_start and seenEpoch < $ts_end ";
    $sql .= "ipv4 != '/0.0.0.0' and ipv4 != '' and seenEpoch >= $ts_start and seenEpoch < $ts_end ";
    $sql .= "order by apMac"
	if ($apMac ne "");
    $sql .= ";";

    my $file = "bogus.sql";
    open(TMP, ">$file")
	|| die "Can't write to $file";
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
    print "Got count: $count\n";

    unlink($file);

    return $count;
}

sub doit {
    my $apMac = shift;
    my $apName = shift;
    my $dt = shift;

    my $date_str = $dt->strftime("%Y-%m-%d");
    print "=== For $apName on $date_str\n";

    my $hour = 0;
    my $results;
    while ($hour < 24) {
	my $e = $dt->epoch() + ($hour * 60 * 60);
	my $hour_dt = DateTime->from_epoch(epoch => $e);
	$results->{$hour} = doit_hour($apMac, $apName, $hour_dt);

	++$hour;
    }

    return $results;
}

#######################################################################

# This makes sqlite3 happy
close(STDIN);

my $date_arg;
my $help_arg;

&Getopt::Long::Configure("bundling");
my $ok = Getopt::Long::GetOptions("date|d=s" => \$date_arg,
				  "help|h" => \$help_arg);

if ($date_arg !~ m/(\d\d\d\d)-(\d\d)-(\d\d)/) {
    $ok = 0;
}

if (!$ok || $help_arg) {
    print "$0 --date YYYY-MM-DD [--help]\n";
    exit($ok);
}

my $year = $1;
my $month = $2;
my $day = $3;

my $d = mktime(0, 0, 0, $day, $month - 1, $year - 1900);
my $dt = DateTime->new(
    year       => $year,
    month      => $month,
    day        => $day,
    hour       => 0,
    minute     => 0,
    second     => 0,
    nanosecond => 0,
    time_zone  => $local_time_zone,
    );

# Collect results for and each location on that date
my $results;
$results->{wc} =
    doit("00:18:0a:79:a5:e2", "WC", $dt);
$results->{eh} =
    doit("00:18:0a:79:8e:2d", "EH Copyroom", $dt);
$results->{both} =
    doit("", "Both", $dt);

print Dumper($results);

#######################################################################

# Remove the old data file, write a new one
my $file = "results.txt";
unlink($file);
open(OUT, ">$file")
    || die "Can't write to $file";

# Grab all the locations
my @locations = sort(keys(%{$results}));

# Write all the data
my $hour = 0;
while ($hour < 24) {
    print OUT "$hour ";
    foreach my $location (@locations) {
	print OUT "$results->{$location}->{$hour} ";
    }
    print OUT "\n";
    ++$hour;
}
close(OUT);

#######################################################################

# Gnuplot it!
# Make a string with the gnuplot commands
# Use the dates as xtics
my $gp;
$gp = "set terminal pdf
set title \"Clients on ECC Meraki AP wifi networks, by hour on $date_arg\"\n";
$gp .= 'set grid
set xlabel "Hour of day"
set ylabel "Number of clients"
set key top left

set xtics border in scale 1,0.5 nomirror rotate by -45  autojustify
set xtics (';
my $num = 0;
foreach my $m (qw/am pm/) {
    my $render;
    if ($m eq "am") {
	$render = "midnight";
    } else {
	$render = "noon";
    }
    $gp .= "\"$render\" $num, ";
    ++$num;

    my $hour = 1;
    while ($hour < 12) {
	$gp .= "\"$hour$m\" $num";
	$gp .= ", "
	    if ($num < 24);
	++$hour;
	++$num;
    }
}
$gp .= ")

set output \"ecc-meraki-data-by-hour-$date_arg.pdf\";
plot ";

# Plot each AP
my $column = 2;
foreach my $location (@locations) {
    $gp .= "\"$file\" using 1:$column with linespoints title \"$location\",";
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
