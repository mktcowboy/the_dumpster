#!/bin/sh
set -eu
cd "$(git rev-parse --show-toplevel)"
git config --local user.name 'Repository Contributor'
git config --local user.email 'contributor@example.invalid'
git config --local core.hooksPath .githooks
