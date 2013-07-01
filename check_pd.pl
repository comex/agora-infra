#!/usr/bin/perl
# if anyone reads this code - it was me learning perl. :p
use strict;
use Data::Dumper;
my %purported_powercounts = ();
my %real_powercounts = ();
my %rtitles = ();
my %ititles = ();
my $ho_p = -1; my $to_p;
my $ho_r; my $to_r;
my $mode = 0;
my $next_is_cat = 0;
#my @cats_p = ();
my @cats_r = ();
my @cats_s = ();
my @inos = ();
my @rnos = ();
my $my_ruleno;
my ($last_hist_prop, $last_hist_time);
my ($last_prop, $highest_prop);
my ($last, $revnum, $ruleno);
$last = $revnum = $ruleno = -1;
my %mentioned = ();
my $garbage = 0;
my $return = 0;
# $. is line number just sayin'
while (<STDIN>) {
    utf8::decode($_);
    chomp;
    if(/ $/) {
		print "space at end: $_\n";   
		$return = 1;
    }
    if(/^.{71}/ && !/[\/\\]/) {
        print "too long: '$_'\n";
        $return = 1;
    }
    if(/^ {3-5}/) {
        print "3-5: $_\n";
        return 1;   
    }
    if($next_is_cat) {
        if(/Garbage/) {
            $garbage = 1;
        } else {
            push(@cats_s, $_);
        }
        $next_is_cat = 0;
    }
    if(/=======/) {
        $next_is_cat = 1;
    }
    if(/Last proposal with recorded effect on this ruleset: ([0-9]+)/m) {
        $last_prop = $1;
    }
    if($ho_p == -1 && /highest.*: ([0-9]+)$/im) {
        $ho_p = $1;
    }
    if(/Current total number of rules: ([0-9]+)/m) {
        $to_p = $1;   
    }
    if(/^\s+([0-9]+) with Power=([0-9\.]+)$/m) {
        $purported_powercounts{ $2 } = $1;
    }
    if(defined $my_ruleno) {
        $rtitles{$my_ruleno} = $_;
        undef $my_ruleno;
    }
    if(/Rule ([0-9]+)\/[0-9]+ \(Power=([0-9\.]+)\)/m) {
        $my_ruleno = $1;
        push(@rnos, $1);
        $real_powercounts{ $2 }++;   
        $to_r++;
        $last_hist_prop = 0;
        $last_hist_time = 0;
    }
    if(/Rule +([0-9]+): (.+)$/m) {
        $ititles{$1} = $2;
        $mode == 1 and push(@inos, $1);
    }
    if(!$garbage && /^(.*)Rule ([0-9]+)/mi) {
        if($1 !~ /^Initial/ && $1 !~ /by $/) {
            $ho_r = $2 if $2 > $ho_r;
            $mentioned{$2} = 1;   
        }
    }
    #if($mode == 0 && /\* (.+)$/m) {
    #    push(@cats_p, $1);
    #}
    if($mode == 1 && /\* (.+)$/m) {
        push(@cats_r, $1);
    }
    if(/Proposal ([0-9]+)/im && $1 != 4781 && $1 > $last_prop) {
        print "never heard of proposal $1\n";
        if($ARGV[1] ne '-f') {
            $return = 1;
        }
    }
    if(/Index of Rules/) {
        $mode = 1;
    } elsif(/as follows/) {
        $mode = 2;   
    }
	if(/Rule ([0-9]+)\/([0-9]+)/m || /^----/ || /^END OF THE FULL LOGICAL RULESET$/) {
		if($revnum != -1 && $last != $revnum) {
			print "Problem with Rule $ruleno/$revnum ($last)\n";
			die;
			$return = 1;
		}
		$revnum = $1 ? $2 : -1;
		$ruleno = $1;
		$last = -1;
	}    
	if(/^(Created|Initial|Enacted)/) {
		$last = 0;
    } elsif(/\.\.\./) {
        $last = -1;
	} elsif(/^amended\(([0-9\.]+)\)( by Proposal ([0-9]+))?/mi) {
		my ($a, $b, $c) = ($1, $2, $3);
		if($last != -1 && !($a > $last && $a <= $last + 1) && !/\(11\) by Proposal 3968/) {
			print "Problem with [$1 / $last] $_\n";
			$return = 1;
		}
		$last = $a;
		if($b) {
		  $last_hist_prop = $c;
		}
	} elsif(/amended\(([0-9\.]+)\)/mi) {
	    if($last != -1 && !($1 > $last && $1 <= $last + 1)) {
	       print "Problem with [$1 / $last] $_\n";
	       $return = 1;
	    }
		$last = $1;

	}
#    print "hi", $purported_powercounts;
}
while((my $key, my $val) = each(%real_powercounts)) {
    if($val != $purported_powercounts{$key}) {
        print "problem with powercount $key... really $val, says $purported_powercounts{$key}\n";
        $return = 1;
    }
}

if(!$return) { while((my $key, my $val) = each(%purported_powercounts)) {
    if($val != $real_powercounts{$key}) {
        print "problem with powercount $key... really $real_powercounts{$key}, says $val\n";
        $return = 1;
    }
} }

if($ho_p != -1 && ($ho_p != $ho_r)) {
    print "highest orderly (purported $ho_p, really $ho_r)\n";
    #$return = 1;
}
if($to_p != $to_r) {
    print "total number (purported $to_p, really $to_r)\n";   
    $return = 1;
}
sub compare {
	my ($type, $a, $b) = @_;
	if(@$a != @$b) {
        print "different number of $type: {@$a} {@$b}\n";
        return 1;
    }
    foreach my $problem (grep { $a->[$_] ne $b->[$_] } 0..@$a) {
		print "$type problem for [$a->[$problem]] [$b->[$problem]]\n";
		return 1;
	}
    return 0;
}
foreach(@rnos) {
    delete $mentioned{$_};
}
foreach(keys %mentioned) {
    print "!! $_\n";   
    $return = 1;
}    
#$return |= compare('category', \@cats_r, \@cats_p);
#$return |= compare('category', \@cats_s, \@cats_p);
$return |= compare('category', \@cats_r, \@cats_s);
$return |= compare('rule no.', \@rnos, \@inos);

my $e; my $equal = keys %rtitles == keys %ititles; $equal &&= $rtitles{$e = $_} eq $ititles{$_} for keys %rtitles;
if(!$equal) {
    print "title of rule $e is weird : [$rtitles{$e}] [$ititles{$e}]\n";   
    $return = 1;
}
exit($return);
