# as input, concatenate the hashes and codebooks
use Digest::SHA (sha1_hex);
while(<>) {
     if (/^Codebook hashes for Proposal ([0-9]+):/ ||
         /^For Proposal ([0-9]+):/) {
          $prop = $1;
          next;
     }
     $hashes{$prop}->{$1} = $2 if /^(.*): ([a-f0-9]{40})/;
     $player = $1 if /(.*):$/;
     if (/^}$/) {
          chomp $codebook;
          if (sha1_hex($codebook) eq $hashes{$prop}->{$player}) {
               print "ok $prop $player\n";
          } else {
               die "bad $prop $player\n";
          }
     } elsif (/^{$/) {
          $codebook = '';
     } else {
          $codebook .= $_;
     }
}
