#!/bin/bash
set -e
export GIT_DIR=flr
if [ ! -e flr ]; then
    mkdir flr
    git init
fi
cvs-fast-export -p -v current_flr.txt,v | git fast-import --force
git repack -ad
