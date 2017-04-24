#!/usr/bin/env perl

use strict;

use Data::Dumper;
use POSIX;
use DateTime;
use DBI;

my $dump_file = shift;

die "Must specify a dumpfile on the command line"
    if (!defined($dump_file));
die "Dumpfile does not exist"
    if (! -r $dump_file);

open(IN, $dump_file) ||
    die "Cannot open dumpfile: $!";
my $dump;
while (<IN>) {
    $dump .= $_;
}
close(IN);
$dump =~ s/VAR1/results/;
my $results;
eval($dump);

#######################################################################

# Remove the old data file, write a new one
my $file;
$file = "results-sundays.txt";
unlink($file);
open(OUT, ">$file")
    || die "Can't write to $file";

# Grab all the dates and locations
my @dates = sort(keys(%{$results}));
my @locations = sort(keys(%{$results->{$dates[$#dates]}}));

# Write all the data
my $num = 1;
my @sundays;
foreach my $date (@dates) {
    # Only include Sundays
    next
        if ($date !~ /-Sun$/);
    push(@sundays, $date);

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
set title "Guests on ECC Meraki AP wifi networks (Sundays only)"
set grid
set xlabel "Date"
set ylabel "Number of guests"
set key top left

set xtics border in scale 1,0.5 nomirror rotate by -45 autojustify
set xtics (';
# Write out the dates for each X tic label
my $num = 1;
my $count = 0;
foreach my $date (@sundays) {
    # Is this a major (0) or minor (1) tic?
    my $level = 1;
    if ($count % 4 == 0) {
	$level = 0;
    }
    ++$count;

    $gp .= "\"$date\" $num $level";
    $gp .= ", "
	if ($num <= $#sundays);
    ++$num;
}
$gp .= ')

set output "ecc-meraki-data-sundays.pdf";
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
