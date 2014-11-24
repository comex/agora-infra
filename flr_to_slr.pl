#!/usr/bin/perl

use warnings;
use strict;

use IO::Handle;

{
	my $peeked_line;
	sub peekline() {
		unless(defined $peeked_line) {
			local $/ = "\n";
			$peeked_line = STDIN->getline;
			die "hit EOF unexpectedly" unless defined $peeked_line;
			die "incomplete line" unless $peeked_line =~ /\n\z/;
		}
		return $peeked_line;
	}
	sub getline() {
		my $line = peekline();
		$peeked_line = undef;
		return $line;
	}
}

getline eq "THE FULL LOGICAL RULESET\n" or die;
print "THE SHORT LOGICAL RULESET\n";
until(peekline =~ /\A---/) {
	my $d = getline;
	if($d =~ /^Highest/) {
		getline eq "\n" or die;
		next;
	}
	if($d =~ /^Last proposal with recorded/) {
		next;
	}
	print $d;
}
getline until peekline =~ /\A===/;


CATEGORY: while(1) {
    my $catname = getline . getline;
    if($catname =~ /Garbage Bin/) {
        while(1) {
            next CATEGORY if peekline =~ /\A===/;
            if(peekline eq "END OF THE FULL LOGICAL RULESET\n") {
                print "END OF THE SHORT LOGICAL RULESET\n";
                die if defined STDIN->getline;
                exit 0;
            }
            getline;
        }
    } else {
        print $catname;
    }
	getline until peekline =~ /\A---/;
	print getline;
	while(1) {
		die unless getline eq "\n";
		
		if(peekline =~ /\A===/) {
			print "\n";
			next CATEGORY;
		}
		if(peekline =~ /\A\[!/) {
            print "\n";
            print getline until(peekline =~ /\]/);
            print getline, getline, getline;
		} else {
    		last CATEGORY unless peekline =~
    			m#\ARule (\d+)/(\d+) \(Power=(\d(?:\.\d+)?)\)( \[.*)?\n\z#;
    		print "\n", getline, getline;
    		die unless getline eq "\n";
    		my $had_any_text = 0;
    		my $had_non_text = 0;
    		while(1) {
    			last if peekline =~ /\A---/;
    			my $para = "";
    			$para .= getline while peekline ne "\n";
    			getline;
    			if($para =~ /\A /) {
    				die if $had_non_text;
    				$had_any_text = 1;
    				print "\n", $para;    			 
    			} elsif($para =~ /\A\[\!/) {
    				$had_any_text = 1;
    				print "\n", $para;
    			} elsif($para =~ /\ACFJ /) {
    				$had_non_text = 1;
    				print "\n", $para;
    			} elsif($para =~ /\A\[|\AHistory:/) {
    				$had_non_text = 1;
    			} else {
    				die;
    			}
		}
		
		die unless $had_any_text;
		print "\n", getline;
		}
	}
}

die unless peekline eq "END OF THE FULL LOGICAL RULESET\n";
print "\nEND OF THE SHORT LOGICAL RULESET\n";
die if defined STDIN->getline;
exit 0;
