# Prior art: executable claims, word-sweeps, and the judgment-agent residue

Condensed from a client engagement's own issue tracker (not this repo, not
published) where the same problem surfaced independently: prose claims going
stale or arriving wrong, and three successive efforts to mechanise catching
it. Client/system-specific detail is stripped; the reasoning and the
falsified attempts are kept, because those are the load-bearing evidence for
this map's design decisions.

## 1. Executable claims (the marker/gate mechanism)

A four-review-round defect pattern motivated this: prose that was true when
written and falsified by a later commit *in the same change* kept shipping,
because nothing in the repo re-checked it. A churn-ranked staleness tool
(this repo's `stale-claims.py` lineage) scored every one of those claims near
zero, by its own documented design — it ranks by time-since-touched, and
claim and code moved together.

What was built: a marker above a fenced code block names a command; the
command runs; its output is diffed against the block. Ported from this
repo's own `verify-docs.py` lineage, with two deliberate departures, both
argued rather than assumed:

- **Runs markers through a shell**, not `shlex.split` — because every claim
  in that repo was a *fact about the repo* (a count, a name list, a file
  set) rather than one program's transcript, and reducing that to
  command-and-output routinely needs a pipe (`| tail -1`, `| sort -u`). The
  trust boundary this costs — a marker runs whatever it names, and the
  repo's markdown becomes part of the attack surface for anyone who can edit
  it — was written down explicitly rather than discovered later, and judged
  acceptable only because the repo was local-only and single-author.
- **Deliberately not diff-scoped**, reversing the instruction the effort was
  chartered under. The reasoning: a rename in code falsified prose in *two
  files the diff never touched* — a marked claim's subject is the code its
  command names, not the file the claim sits in, so diff-scoping-by-file
  would have missed the motivating failure. This holds only because the
  sweep itself is cheap (a couple of test runs, a handful of greps) — the
  premise that made scoping necessary elsewhere doesn't hold when the whole
  check costs a fraction of a second.

Other findings worth carrying:

- **A verdict function must distinguish "0 checked, 0 failures" from a clean
  pass.** A tool whose only output is a diff will report a clean sweep when
  pointed at nothing — a silent skip that looks like a passing grade. This
  bit the tool itself twice (once for the whole sweep, once for a narrower
  sub-check), and the fix each time was the same: "nothing was checked" is
  its own failure mode, not folded into "0 out of date."
- **Which claims are markable is itself a finding worth recording.** A claim
  needing a credential or network access to verify is not markable in a
  system that must never prompt for one; the honest output is a documented
  list of what was found unmarkable, not a check that quietly skips them.
- **A tool that only compares text has no channel for "this found a
  problem" distinct from "this output changed."** A citation-checker's
  finding could be defeated by pasting the very line that reported it,
  because the checker only diffed old-output-vs-new-output. The fix was a
  second channel: a non-zero exit is a failure in its own right, independent
  of whether the printed text matches or differs.
- **Extraction logic living inside a shell one-liner in a marker cannot be
  unit tested**, and every regression across several review rounds traced
  back to exactly that: a `sed`/`awk`/`grep` pattern hand-tuned to the one
  counterexample a reviewer had just supplied, blind to the next one. The
  fix each time was to move the logic into a small tested script (reading a
  source file's syntax tree rather than pattern-matching it) and have the
  marker call the script — the marker becomes a path, not a program.
- **A repeated review finding, independent of any one tool**: the worst
  defect in several consecutive rounds was *inside the previous round's own
  fix*. Reviewing a change without also reviewing its repair misses the
  failure mode where the fix reintroduces (or merely relocates) the original
  defect.
- **Numbers describing the tree (test counts, line counts, character
  counts) go stale within the session that wrote them and should not be
  recorded at all** — they're re-derivable, so writing one down is pure risk
  with no offsetting benefit. Numbers that measure the *world* (a run count
  against an external system, a byte-for-byte comparison across time) are
  the exception, because they can't be re-derived from the tree.
- **A wall-clock timing figure is a property of the machine and the hour,
  not of the repository**, and is not a claim the repo can hold — after four
  attempts at stating a bound (a point value, then a range, then a range a
  later run fell outside, then a round-number ceiling a reviewer falsified
  the same day), the durable form named no figure at all: "seconds, mostly
  one dominant step" — true regardless of which machine runs it.

## 2. The word-sweep (totalising/count language)

A distinct, narrower failure class: claims that are false against a table or
figure *in the same document*, not because anything drifted, but because the
writer generalised past what they'd actually checked — "every run scores 5 of
5" when one run scored 3; "all fifteen" when the true count was twenty. This
needs no judgment to catch, only a word list: totalising words (*every*,
*only*, *never*), spelled-out or digit counts, and words that assert
something "elsewhere" reported only next to a citation-shaped token.

A tool solving exactly this already existed in a private, separately-licensed
sibling project by the same author, built for the identical failure
independently. Adapting rather than copying it surfaced real differences:

- Its count-word list had a ceiling the new corpus routinely exceeded; the
  fix was mechanical (extend the list) but not a footnote — the numbers a
  corpus actually uses have to be checked, not assumed.
- It could only check the repository it lived in — pointed at a different
  tree, its entry point ignored the argument. Getting it running elsewhere
  meant importing its functions directly, which is closer to "the port is
  the work" than "the port is a wrapper."
- Restricting matches to *whole sentences* in specifically-scoped record
  files, rather than *paragraphs* everywhere, cut the false-positive rate by
  roughly three-quarters with no loss of true findings — the unit of
  analysis mattered more than tuning the word lists.
- **A confounder specific to any repo that records its own defects
  verbatim**: a sweep over a document that quotes a retired false claim
  (to explain what was wrong with it) fires on the quotation, indistinguishable
  from a live assertion. The fix was to recognise the house style used for
  retiring a sentence (an italic, a block quote, a fixed lead-in phrase) and
  suppress on that shape.
- **A number that describes the world, not the tree, is not what the count
  tier exists to catch** — every genuine finding across one large evaluation
  came from the *totalising* words, never the count tier; the one count
  defect found was a tally of review rounds in the record itself, which a
  separate rule already forbade outright, and no count-word list would have
  ranked it above the dozens of legitimate world-measuring numbers on the
  same page.
- **A fourth tier, distinct from both**: claims about a live, queryable
  backend — checkable by one call to it and by nothing else, and wrong in a
  way that produces a confidently-wrong answer to a real question rather
  than a merely stale sentence. Neither a word list nor a diff catches this;
  it needs the system asked directly.

**The licensing question this raised, argued rather than assumed.** The
sibling project's code is proprietary; a design and its ideas are not
copyrightable, but a *curated word list*, hand-tuned with reasoning recorded
beside each entry, is the kind of judgment-driven compilation that can
attract its own protection separately from the tool around it — a much
weaker case for "just reimplement the idea" than usual. Two routes were
identified: relicense the original at its source and port it with full
attribution (the same shape already used for the executable-claims marker
above), or implement independently from the design with no line of the
original list copied — and even the second route isn't automatically clean,
since the boundary between an idea and its expression is a judgment call best
made by, or with explicit sign-off from, whoever holds the rights. The
recommendation was the first route; copying the file in unlicensed was ruled
out under either analysis.

**Advisory vs. gate is a convention worth keeping, not re-deciding per
tool**: the source project splits its tooling directory by exit-code
contract — one directory's tools are candidate lists that always exit 0 and
say so explicitly ("a list to answer, not a verdict"); a sibling directory's
tools gate, and one of them exits with a distinct code specifically when it
can't see enough history to answer honestly, on the principle that a check
which reports clean because it can't see is worse than no check. A
totalising-word sweep belongs in the first category — it will flag some true
sentences by construction, so it cannot gate without breaking the build on
correct prose.

## 3. The judgment-agent residue (claims no command settles)

Once the mechanical checks above exist, what's left is prose describing a
system's architecture or design intent that no command and no word list can
adjudicate — "component X owns responsibility Y", "a caller must always name
the thing explicitly" — where judging truth means reading the actual
implementation and comparing it to the claim.

Two constraints, both learned by direct failure rather than assumed up
front:

- **It must execute or read the artifact, never grep the prose describing
  it.** A prior, unrelated attempt to classify a batch of run logs by
  grepping them for a handful of expected failure-signature strings reported
  every single run as a failure — because those exact strings occur
  ambiently in the loaded documentation and tooling output every run carries
  regardless of outcome, not just in the runs that actually failed. Grepping
  vocabulary that appears in innocuous boilerplate produces a confident,
  uniformly wrong answer, not a noisy one.
- **Every verdict must cite evidence** — a `file:line` or the exact command
  run — because a verdict of "looks fine" with nothing behind it is the
  output that makes the entire exercise worthless, and is the specific
  failure a much earlier, purely-instructional guideline had already been
  written to prevent (and had already failed to prevent, which is why a
  mechanical check was wanted at all).

**The open problem, not yet solved anywhere surveyed**: bounding the list of
candidates this judgment layer spends attention on. A sweep must never issue
a clean "all good" verdict — a periodic check that reports nothing most runs
trains its own reader to stop reading it — so it has to rank candidates, the
same discipline the churn-ranker already follows. But the two obvious
candidate-list mechanisms both fail this repo's dominant failure mode:
diff-scoping-by-file under-selects (see §1's motivating rename, which
falsified prose in files the diff never touched), and churn-ranking is blind
to the case where a claim and the code it describes move in the same commit
(see §1 again — the same blind spot that motivated the executable-claims
marker in the first place). The right shape is closer to "prose whose
*subject* the diff touched" rather than "prose in a file the diff touched" —
deriving what a subject is and how to diff it between two revisions was
identified as the hard part still open, not yet built.

**What made a fully unattended version of this seem feasible at all**: an
adjacent, differently-scoped scheduled process (unrelated to claims-checking)
had by that point run to completion many dozens of times unattended, and,
unlike that process, a claims-judgment pass needs no credentials — so the
one thing that kept the existing scheduled process semi-attended (a
credential-vault prompt) doesn't apply here. That's evidence the mechanism
*could* run unattended, not a reason to put it on a timer — the same source
found that a periodic sweep reporting nothing most nights is worse than no
sweep, and any version of this should rank candidates for someone to read
rather than emit its own periodic verdict.
