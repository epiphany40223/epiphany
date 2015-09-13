#!/usr/bin/env perl

use strict;
use warnings;

use File::Basename;
use Cwd;
use Data::Dumper;
use Getopt::Long;

###############################################################################

my $user = "epibot";
my $pw;
my $srcuri = '\\\\fileengine\pdschurch';
my $srcdir = "data";
my $destdir = "$ENV{HOME}/epiphany/pdschurch/data";
my $debug_arg = 0;
my $help_arg = 0;

&Getopt::Long::Configure("bundling");
my $ok = Getopt::Long::GetOptions("user=s" => \$user,
                                  "pw=s" => \$pw,
                                  "src-uri=s" => \$srcuri,
                                  "src-dir=s", \$srcdir,
                                  "dest-dir=s", \$destdir,
                                  "debug" => \$debug_arg,
                                  "help|h" => \$help_arg);
if (!$ok || $help_arg) {
    print "$0 --pw=SMB_PW [user=SMB_USER] [--src-uri=SRC_URI] [--src-dir=SRC_DIR] [--dest-dir=DEST_DIR] [--debug]\n";
    exit(0);
}

###############################################################################

die "Must specify a password"
    if (!defined($pw));

###############################################################################

my $ddir = dirname($destdir);
if (-d $ddir) {
    chdir($ddir);
    my $bdir = basename($destdir);
    system("rm -rf $bdir");
    mkdir($bdir);
    chdir($bdir);
} else {
    system("mkdir -p $destdir");
    chdir($destdir);
}

print "==> Emptied dir " . getcwd() . "\n"
    if ($debug_arg);
die "Something went wrong; I am not in $destdir"
    if (getcwd() ne $destdir);

my @cmd = qw/smbclient/;
push(@cmd, $srcuri);
push(@cmd, "--user=$user");
push(@cmd, $pw);
push(@cmd, "-c");

print "==> Testing Samba URI $srcuri, user=$user, pw=$pw\n"
    if ($debug_arg);
my @test = @cmd;
push(@test, "ls");
push(@test, ">/dev/null")
    if (!$debug_arg);
print Dumper(@test)
    if ($debug_arg);
my $rc = system(@test);
die "Samba client failed; did you specify the right username password and URI?"
    if (0 != $rc);

print "==> Test ok; doing actual copy to $destdir\n"
    if ($debug_arg);

push(@cmd, "prompt; cd $srcdir; mget *");
push(@test, ">/dev/null")
    if (!$debug_arg);
print Dumper(@cmd)
    if ($debug_arg);
$rc = system(@cmd);
die "Copy from SMB failed!"
    if ($rc != 0);

print "==> Copy completed successfully\n"
    if ($debug_arg);

exit(0);
