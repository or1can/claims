#!/bin/sh
# Tags the current commit with the version in VERSION, then pushes the
# branch and the tag together.
set -e
version=$(cat VERSION)
git tag -a "v$version" -m "Acme $version"
git push --follow-tags
