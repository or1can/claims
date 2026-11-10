#!/bin/sh
# PROTOTYPE for #215 — throwaway, wipe me. Runs the tour arc in a temp repo
# and prints a transcript: "$ cmd" then its combined output and exit code.
set -u
CHECKOUT=$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)
[ -n "${CLAIMS_CHECKOUT:-}" ] && CHECKOUT=$CLAIMS_CHECKOUT
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=Reader GIT_AUTHOR_EMAIL=reader@example.com
export GIT_COMMITTER_NAME=Reader GIT_COMMITTER_EMAIL=reader@example.com
export GIT_AUTHOR_DATE=@1700000000 GIT_COMMITTER_DATE=@1700000000
export PYTHONPATH=$CHECKOUT
run() { printf '$ %s\n' "$*"; sh -c "$*" 2>&1; printf '[exit %s]\n\n' "$?"; }

mkdir "$T/hooks"
cat > "$T/hooks/pre-commit" <<'H'
#!/bin/sh
exec python3 -P -m claims.pre_commit
H
cat > "$T/hooks/pre-push" <<'H'
#!/bin/sh
exec python3 -P -m claims.cli --diff-range origin/main...HEAD --fail-on-unmarked
H
chmod +x "$T/hooks/"*

git init -q --bare -b main "$T/remote.git"
git init -q -b main "$T/work"
cd "$T/work"
git remote add origin ../remote.git
mkdir scripts
printf '#!/bin/sh\necho releasing\n' > scripts/release.sh
printf '1.0.0\n' > VERSION
cat > README.md <<'F'
# Acme

Current version:

<!-- verify: cat VERSION -->
```
1.0.0
```
F
cat > spec.md <<'F'
# Release process
F
printf '[claim-words]\nfiles = ["spec.md"]\n' > claims.toml
printf '[executable-claims]\nallowed = ["cat VERSION"]\n' > claims.local.toml
printf 'claims.local.toml\n' > .gitignore
git add -A && git commit -q -m "Start" && git push -q -u origin main 2>/dev/null
git config core.hooksPath "$T/hooks"

# Beat 1: a wrong doc, refused at commit.
cat > README.md <<'F'
# Acme

Current version:

<!-- verify: cat VERSION -->
```
1.0.0
```

To cut a release, run `scripts/deploy.sh`.
F
cat > spec.md <<'F'
# Release process

Every release is tagged before it is pushed.
F
run git add README.md spec.md
run git commit -m '"Document releasing"'
run "sed -i.bak 's/deploy.sh/release.sh/' README.md && rm README.md.bak && git add README.md"
run git commit -m '"Document releasing"'
# Beat 2: the push fails on the unmarked advisory, a checked mark unblocks it.
run git push
run "echo 'spec.md:3 claim-words-totalising scripts/release.sh tags before pushing' | python3 -P -m claims.cli mark-checked --diff-range origin/main --by Reader"
run cat claims.checked.toml
run "git add claims.checked.toml && git commit -m 'Mark the release claim checked'"
run git push
