$v = "\t";
@more = ();
$who = "?";
sub end {
    print "$v\n" if $v ne "\t";
}
while(<>) {
    next if /^\s*$/;
    if (/^- (.*)$/) {
        end();
        $who = $1;
        $v = "$1\t";
    }
    if($pn) {
        if(/^(AGAINST|FOR|PRESENT)/) {
            $v .= substr($1, 0, 1) . "\t";
        } elsif(/^PASS$/) {
            $v .= "\t";
        } else {
            $v .= "?\t";
        }
        if(!/^(AGAINST|FOR|PRESENT)$/) {
            push(@more, "** $pn $who $_");
        }
    }
    $pn = /^(> )?([0-9]{4})/ ? $2 : "";
}
end();
map { print } (sort @more);
