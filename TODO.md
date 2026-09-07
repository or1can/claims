# TODO

- `claims/checks/executable_claims.py`'s `ls-files` call
  (`.stdout.split()`) has the same whitespace-splitting bug fixed in
  `stale-claims` (ticket 08 code review): a tracked `*.md` filename
  containing a space would be shredded into two bogus paths. Not fixed
  here — out of ticket 08's scope, noted for whichever ticket next touches
  `executable_claims.py`.
