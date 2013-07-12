#!/bin/bash
python pmsince.py iw/downloads "$1" | case "$2" in
    -prop) fu -v 'Subject: OFF:.*(Logical Ruleset|Distribution of Proposals|Promise Report)' | fu -ci '(?<!distribution of )propos|(retract|submit|withdraw)(?!s)|\b(ai|pf)[ =]\b' ;;
    -vote) fu -v 'Subject: OFF:' | fu -c '\bFOR\b|(?i)\bagainst\b|\b7[0-9]{3}\b|vote|Subject:.*Distribution of Proposals' ;;
    *) nope ;;
esac
