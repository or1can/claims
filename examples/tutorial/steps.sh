# The commands docs/tutorial.md shows, one per line, and the commands
# scripts/tutorial.py capture runs. Each step sits between an mdBook
# anchor pair the page includes it by. `setup` runs from the clone's
# root, every later step from .tutorial/acme. One command per line, each
# run on its own with `sh -c`: no heredocs, no continuation lines.

# ANCHOR: setup
uv run -q scripts/tutorial.py setup
# ANCHOR_END: setup

# ANCHOR: commit
git add RELEASING.md
git diff --cached
git commit -m "Document releasing"
# ANCHOR_END: commit

# ANCHOR: fix
git diff
git add RELEASING.md
git commit -m "Document releasing"
# ANCHOR_END: fix

# ANCHOR: push
git push
# ANCHOR_END: push

# ANCHOR: mark
cat scripts/release.sh
echo 'RELEASING.md:12 claim-words-totalising scripts/release.sh runs git tag before git push' | uv run -q python -m claims.cli mark-checked --diff-range origin/main
cat claims.checked.toml
git add claims.checked.toml
git commit -m "Mark the release claim checked"
# ANCHOR_END: mark

# ANCHOR: push-again
git push
# ANCHOR_END: push-again
