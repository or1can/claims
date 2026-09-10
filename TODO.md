# TODO

Items that used to live here and have since become tracked tickets:
ticket 26 (`check_links.py` underscore-slug bug), ticket 27
(`added_lines_by_file` diff-header prefix), ticket 28 (`runner.run()`
exception isolation), ticket 29 (`check_citations._declared_ever`
caching), ticket 30 (`known_true` golden-fixture flake investigation).
See `.scratch/claims-consolidation/issues/` for each.

`claims/checks/claim_words.py`'s `_is_retired_quote` promotion note
(originally: "promote to a shared module if a future check needs the same
judgment") is dropped — ticket 11's `spliced-docs` shipped without needing
it, so the anticipated second consumer never materialized.
