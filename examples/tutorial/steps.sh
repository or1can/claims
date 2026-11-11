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
