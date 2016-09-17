#!/usr/bin/env perl

use strict;

use POSIX;
use DateTime;

sub doit {
    my $apMac = shift;
    my $apName = shift;
    my $dt = shift;

    my $date_str = $dt->strftime("%Y-%m-%d");

    print "=== For $apName on $date_str\n";

    my $file = "bogus.sql";
    open(TMP, ">$file")
        || die "Can't write to $file";
#    print TMP ".load /usr/lib/sqlite3/pcre.so\n";

    my $sql = "select distinct clientMac,ipv4,manufacturer from data where ";
    $sql .=  "apMac = '$apMac' and "
        if ($apMac ne "");
    $sql .= "ssid='Epiphany (pw=epiphany)' and ipv4 != '/0.0.0.0' and seenTime glob '$date_str*' ";
    $sql .= "order by apMac"
        if ($apMac ne "");
    $sql .= ";";

    print "SQL: $sql\n";
    print TMP "$sql\n";
    close(TMP);

    open(SQL, "sqlite3 /home/jeff/ecc-meraki-data/data.sqlite3 -init $file|")
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
my $d = mktime(0, 0, 3, 6, 9 - 1, 2016 - 1900);
my $dt = DateTime->new(
    year       => 2016,
    month      => 9,
    day        => 12,
    hour       => 0,
    minute     => 0,
    second     => 1, # Just to make sure we're in that day
    nanosecond => 0,
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

# Remove the old file, write a new one
my $file = "results.txt";
unlink($file);
open(OUT, ">$file")
    || die "Can't write to $file";

# Write title row
# (just grab any date so that we can get the location keys)
my @dates = sort(keys(%{$results}));
my @locations = sort(keys(%{$results->{$dates[0]}}));
#print OUT "# date,";
#foreach my $location (@locations) {
#    print OUT "$location,";
#}
#print OUT "\n";

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

my $column = 3;
foreach my $location (@locations) {
    $gp .= "\"$file\" using 2:$column with linespoints title \"$location\"";
    $gp .= ", "
        if ($column - 3 < $#locations);
    ++$column;
}

$gp .= "
quit\n";

# Plot it
open(GP, "|gnuplot") || die "Can't open gnuplot";
print $gp;
print GP $gp;
close(GP);

# All done!
exit(0);
