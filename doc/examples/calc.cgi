#!/usr/bin/perl

use strict;
use warnings;

use CGI;

my $q = CGI -> new();

$q->import_names;
my $op = $Q::op;
my $a = $Q::a;
my $b = $Q::b;

my $ops = {
    add => sub { $_[0] + $_[1] },
    sub => sub { $_[0] - $_[1] },
    mul => sub { $_[0] * $_[1] },
    div => sub { $_[0] / $_[1] },
};

if (defined $ops->{$op}) {
    print "Content-type: text/plain\n\n";
    print $ops->{$op}->($a, $b);
    print "\n";
} else {
    warn "unsupported operator: $op\n";
}
