# Writing marks from reading-agent output

No command turns the reading agent's JSON into checked marks. The session
that asked for a reading reads its evidence and writes the marks itself,
by the check-claims skill's step 8.

## Why this is out of scope

#276 asked for a deterministic translator, for example `mark-checked
--from-readings <file>`, so that the skill's rule from verdicts to a
full or partial mark and its `--kind` isn't applied by hand. Three things
stand in the way.

**The hand mapping was not where marks went wrong.** Triage compared the
marks written from `9976096`, the commit that added `--kind`, to
`2e545f7` with the reading agent's reports in one machine's session
transcripts. Of 343 marks naming the agent as a reader, 264 matched a
report, and 232 of those were what the rule gives for the latest one
before them. In 24 of the other 32, `by` also names the session, which
settled or overrode a claim; those were not checked one by one. One of
the remaining 8 was wrong, a full mark in `05d6499` on a `TODO.md`
`claim-words` finding whose note says which claims were left unread. The
session knew that and marked anyway, so a translator that refused the
report would not have stopped it: plain `mark-checked` would still have
taken the entry. The mark was gone by the next commit to write the file.
The 79 marks that matched no report were not checked.

**The latest report is often not the whole reading.** A finding re-sent
for its trees can come back with one claim where the first pass had
thirteen, as ADR 0019's Decision did for `338a4f6`. Translated alone,
that report marks the whole section superseded, and a superseded mark
doesn't expire with its subjects. Merging the two needs claims matched
by their quoted text, which the agent quotes differently each time. The
session also settles what the agent couldn't reach (the skill's step 7),
which changes verdicts, `by` and the note after the JSON is written.

**The output isn't input for a command.** `kind_evidence` is prose around
a `file:line`: in 216 past or superseded claims, none named the
`page.md#anchor` section that `--evidence` takes. `finding` was not a
plain `file:line` and mode in 129 of 358 reports; some named two modes
at once. Making both strict changes the agent's contract, which its
golden runs would have to prove again.

What is left for a translator is a finding whose claims are all true and
current. That is already the form with no flag to get wrong.

A future request would need one of these:

- a wrong `--kind` or extent that came from translating the agent's
  output, not from marking a claim known to be unread;
- the agent's `finding` and `kind_evidence` made strict for another
  reason, with a rule for merging two reports on one finding.

## Prior requests

- #276: "Write marks from reading-agent output by the skill's rule"
