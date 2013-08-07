my %data = ();
my @proposals = ();
my @skipped = ();
my $have_control;
my $is_control;
my $mi = 1000;

my $proptext = qr/Create|Amend|Repeal/i;

use Data::Dumper;
use Text::Wrap;
use List::Util qw(max);

sub default {
    $data{"AI"} = 1;
    $data{"PF"} = 0;
    $data{"ID"}++;
    $data{"co-authors"} = [];
    $data{"text"} = "";
    $data{"title"} = "";
    $data{"chamber"} = "Ordinary";
    $data{"braces"} = 0;
    $data{"skip"} = 0;
    #$data{"interest"} = 1;
}

default();

sub control {
    if($data{"text"}) {
        if($data{"braces"}) {
            $data{"text"} =~ s/(}}?}?\.?)?\s*$//s;
        }
        $data{"text"} =~ /^[\s=-]*(.*?)[\s=-]*\s*$/s;
        $data{"text"} = $1;
        $data{"text"} = $1;
        $data{"author_etc"} = $data{"author"} . (@{$data{"co-authors"}} ? ", etc." : "");
        $data{"title"} ||= "(untitled)";
        $data{"interest"} = $data{"PF"} > 0;
        my %other = %data;
        if(!$data{"skip"} && (!$data{"interest"} || $mi-- > 0)) {
            push(@proposals, \%other);
        } else {
            push(@skipped, $data{"title"});
        }
        default();
    }
    $have_control = 1;
}

my $bracket = 0;

lines:
while(<>) {
    next if /^\/\//;
    $have_control = 0;
    $bracket++ if(/^\[/);
    unless(/^ / || /^amend/i|| s/^\^\^// || $bracket) { # exempt rule text
        $is_control = 0;
        if(/(AI|adoption index)\W+([0-9\.]+)/i) {
            control();
            $data{"AI"} = $2;
        }
        if(/(PF|proposal fee)\W+Y?\W*([0-9]+)/i) {
            control();
            $data{"PF"} = $2;
        }
        if(/disi/i) {
            control();
            #$data{"interest"} = 0;
        }
        #if(/titled? ['"{]\s*(.*?)\s*['"}]/i) {
        #    control();
        #    $data{"title"} = $1;
        #}
        if(/^- (.*)$/) {
            control();
            for(split /\s+/, $1) {
                last lines if($_ eq "DIE");
                s/_/ /g;
                if(/^q=([0-9]+)$/) {
                    $quorum = $1;
                } elsif(/^mi=([0-9]+)$/) {
                    $mi = $1;
                } elsif($_ eq "skip") {
                    $data{"skip"} = 1;
                } else {
                    $data{/^[0-9]{4}$/ ? "ID" : "author"} = $_;
                }
            }
        }
        if(/co-?authors?\W+([^\)]+?)(, [^,]*=)?[\),]/i) {
            control();
            push @{$data{"co-authors"}}, (split /\s*,\s*/, $1);
        }
        if(!$data{"text"} && /[{}]/ && !/$proptext/) {
            control();
            $data{"braces"} = 1;
            if(/{{\s*([a-z][^\(]+)/i) {
                $data{"title"} = $1;
                $data{"title"} =~ s/\s+$//;
            }
        }
        if(#!/^[\[\(]/ &&
           (!$data{"title"} || $data{"text"}) && (
            /(^\s*|submit.*)proposal[^:].*"([^"]*)"/i ||
            /^\s*proposal(,|[^"]*?:)[\s:,]*"?([^\(:]+[^\s\(":])/i ||
            /^{ (([^\(,]*))( \(|, )/i ||
            /^(([^\(,]*))( \(|, )(ai|disi|pf)/i ||
            ((/submit.*proposal,\s*(([^,]+)),\s*AI/i ||
              /submit.*proposal(.*["{](.*?)["}])?/i) &&
             !/submit proposals/i))) {
            control();
            if($1) {
                $data{"title"} = $2;
                $data{"title"} =~ s/,\s*(AI|co[a-]).*$//;
            }
        }
        if($is_control) {
            for $chamber ("Democratic", "Ordinary", "Gerontocratic", "Star") {
                if(index($_, $chamber) != -1) {
                    $data{"chamber"} = $chamber;
                }
            }
        }
    }

    $bracket-- if($bracket && /\]/);

    if(!$data{"text"} &&
        /^[-=\s]*$/) {
        $have_control = 1;
    }

    #print "$have_control $_";

    if(!$have_control) {
        $data{"text"} .= $_;
    }
}

control();

if(@skipped) {
    print "* PROPOSALS SKIPPED: " . join(', ', @skipped) . " *\n\n";
}

print "I hereby distribute each listed proposal, initiating the Agoran
Decision of whether to adopt it.  For this decision, the eligible
voters are the active first-class players at the time of this
distribution, the vote collector is the Assessor, and the valid
options are FOR and AGAINST (PRESENT is also a valid vote).

Quorum is $quorum.

Pool report: The Proposal Pool is empty (and no proposals have nonzero
Distributability).

";

$author_len = max(max(map {length($_->{"author_etc"})} @proposals) + 2, 12);

print 'NUM  AI  PF C AUTHOR' . " " x ($author_len - 6) . "TITLE\n\n";

for(@proposals) {
    printf "%-5s%-3s%3s %.1s %-${author_len}s", $_->{"ID"}, $_->{"AI"}, $_->{"PF"}, $_->{"chamber"}, $_->{"author_etc"};
    $Text::Wrap::columns=70 - ($author_len + 14);
    $title = wrap("", "", $_->{"title"});
    $spaces = "." x 6 . " " x ($author_len + 14 - 6);
    $title =~ s/\n/\n$spaces/g;
    print "$title\n";
}

for(@proposals) {
    print "\n}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{\n\n";
    printf "Proposal %s (AI=%s, PF=Y%d, %s) by %s", $_->{"ID"}, $_->{"AI"}, $_->{"PF"}, $_->{"chamber"}, $_->{"author"};
    for(@{$_->{"co-authors"}}) { print ", $_"; }
    printf "\n%s\n\n%s\n", $_->{"title"}, $_->{"text"};
}
