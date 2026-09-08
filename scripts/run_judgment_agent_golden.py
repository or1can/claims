# Copyright 2026 Orican Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Golden-fixture harness for the judgment-agent subagent's verdict half.

Ticket 15's own test criterion is explicit that this half needs "behavioral/
golden fixtures ... not unit tests, since the subagent's output is
LLM-driven rather than a pure function" (spec.md's Testing Decisions). This
script is that harness: it shells out to a live `claude -p` invocation per
fixture under `tests/fixtures/judgment_agent_golden/`, which costs a real API
call and is not guaranteed deterministic across model versions.

Deliberately **not** collected by `unittest discover -s tests -p 'test_*.py'`
(it lives under `scripts/`, not `tests/`, and isn't named `test_*.py`) —
run it by hand: `python3 scripts/run_judgment_agent_golden.py`.

Runs with `--output-format stream-json` rather than the single-shot `json`
format so this harness can inspect the subagent's own tool calls, not just
its final verdict — the ticket's own criterion is that the subagent "does
not grep for vocabulary describing the claim as its evidence-gathering
method, verified by checking it reads/executes the actual code path", which
a verdict string alone can't establish: a lucky grep-and-hallucinate could
produce a correct-looking verdict without ever reading the code.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SUBAGENT_PROMPT = REPO_ROOT / "claims" / "subagent" / "judgment_agent.md"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "judgment_agent_golden"

_STOPWORDS = {
    "a", "an", "the", "is", "in", "of", "to", "so", "see", "and", "or",
    "for", "this", "that", "its", "it", "on", "by", "as", "from",
}


def _system_prompt() -> str:
    text = SUBAGENT_PROMPT.read_text(encoding="utf-8")
    # Strip the `---`-delimited YAML frontmatter; `claude -p` takes the
    # subagent's instructions as a system prompt, not its Claude Code
    # frontmatter (name/description/tools are for agent *discovery*, which
    # this harness bypasses by invoking the prompt directly).
    _, _, body = text.partition("---\n")
    _, _, body = body.partition("---\n")
    return body.strip()


def _extract_verdict(result_text: str) -> dict[str, Any]:
    # A balanced-brace scan from the first `{`, not a greedy regex — a
    # regex spanning first-`{`-to-last-`}` would silently grab the wrong
    # span if the model ever wraps the object in extra text despite being
    # told to output nothing else. String-aware (tracks quotes and escapes)
    # so a `{`/`}` inside a JSON string value — e.g. a `reasoning` field
    # quoting code like `self._store = {}` — doesn't desync the depth count.
    start = result_text.find("{")
    if start == -1:
        raise ValueError(f"no JSON object found in subagent output: {result_text!r}")
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(result_text[start:], start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(result_text[start : index + 1])
    raise ValueError(f"unbalanced JSON object in subagent output: {result_text!r}")


def _cited_file(claim: str) -> str | None:
    """The first backticked, filename-shaped token in the claim (e.g. `cache.py` out of `` `cache.py:4` ``)."""

    for token in re.findall(r"`([^`]+)`", claim):
        name = token.split(":")[0]
        if "." in name:
            return name
    return None


_SUFFIXES = ("ization", "ational", "tion", "ing", "ed", "es", "s")


def _stem(word: str) -> str:
    """Strip one trailing suffix — enough to match "threads" against a Grep
    for "thread", not a real lemmatizer. A stemmed match is still only a
    heuristic: it won't catch every synonym or inflection, only the plain
    plural/verb-form case this check exists to close."""

    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _forbidden_vocabulary(claim: str) -> set[str]:
    """The claim's own descriptive prose, as stemmed words, minus its backticked citations and stopwords.

    Citations (backticked symbol/file names) are legitimate Grep/Glob
    targets — locating a subject by its exact name is the check's job. This
    is everything else: the adjectives and generalizations ("thread-safe",
    "every", "without") a real evidence-gathering pass has no business
    searching for.
    """

    without_citations = re.sub(r"`[^`]*`", " ", claim)
    words = {w.lower() for w in re.findall(r"[A-Za-z]+", without_citations)}
    return {_stem(w) for w in words - _STOPWORDS}


def _tool_calls(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "tool_use":
                calls.append(block)
    return calls


def _run_fixture(fixture_dir: Path, system_prompt: str) -> tuple[bool, str]:
    claim = (fixture_dir / "claim.md").read_text(encoding="utf-8").strip()
    expected = json.loads((fixture_dir / "expected_verdict.json").read_text(encoding="utf-8"))
    repo_dir = fixture_dir / "repo"

    message = (
        f"Candidate claim (from claim.md, in the current working directory's "
        f"parent):\n\n{claim}\n\nThe code it cites is in this working "
        f"directory. Produce your verdict."
    )

    done = subprocess.run(
        [
            "claude",
            "-p",
            message,
            "--append-system-prompt",
            system_prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--allowedTools",
            "Read,Glob,Grep",
        ],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        return False, f"claude exited {done.returncode}: {done.stderr.strip()}"

    events: list[dict[str, Any]] = [
        json.loads(line) for line in done.stdout.splitlines() if line.strip()
    ]
    result_event = next((e for e in events if e.get("type") == "result"), None)
    if result_event is None:
        return False, f"no result event in stream-json output: {done.stdout!r}"

    try:
        verdict = _extract_verdict(str(result_event.get("result", "")))
    except ValueError as exc:
        return False, str(exc)

    if not verdict.get("evidence"):
        return False, f"no evidence cited: {verdict!r}"
    if verdict.get("verdict") != expected["verdict"]:
        return False, f"expected verdict {expected['verdict']!r}, got {verdict!r}"

    tool_calls = _tool_calls(events)

    forbidden = _forbidden_vocabulary(claim)
    for call in tool_calls:
        if call.get("name") != "Grep":
            continue
        pattern = str(call.get("input", {}).get("pattern", "")).lower()
        pattern_words = {_stem(w) for w in re.findall(r"[A-Za-z]+", pattern)}
        hit = forbidden & pattern_words
        if hit:
            return False, f"Grep pattern {pattern!r} used claim vocabulary {sorted(hit)!r}, not a symbol lookup"

    # Require an actual `Read` of the cited file, not merely a tool call
    # that *names* it (e.g. a `Grep` scoped to that path) — a grep-the-
    # symbol-and-count-hits strategy never reads the code and must not pass.
    cited_file = _cited_file(claim)
    read_paths = [
        str(call.get("input", {}).get("file_path", ""))
        for call in tool_calls
        if call.get("name") == "Read"
    ]
    if cited_file and not any(cited_file in path for path in read_paths):
        return False, f"no Read call opened the cited file {cited_file!r} — Read calls: {read_paths!r}"

    return True, f"verdict={verdict['verdict']!r} evidence={verdict['evidence']!r}"


def main() -> int:
    system_prompt = _system_prompt()
    fixture_dirs = sorted(p for p in FIXTURES_DIR.iterdir() if p.is_dir())
    if not fixture_dirs:
        print(f"no fixtures found under {FIXTURES_DIR}", file=sys.stderr)
        return 2

    failures = 0
    for fixture_dir in fixture_dirs:
        ok, detail = _run_fixture(fixture_dir, system_prompt)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {fixture_dir.name}: {detail}")
        if not ok:
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
