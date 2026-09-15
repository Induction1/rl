# pokeval

An eval where a coding agent (Claude Code, in a sealed Docker container) gets two hours to write a Generation 1
Pokémon battle engine in Python whose battle logs match Pokémon Showdown's, graded on a held out set of 1,000
battles. Share of test turns matched at 120 minutes of work: Opus 5 73.7, Opus 4.8 39.1, Opus 4.7 29.1, Sonnet 5
28.0, Opus 4.6 7.0, Sonnet 4.6 3.4.

Read more at https://induction1.github.io/research/pokemon-engine-eval/

## Layout

| Folder | What is in it |
|---|---|
| `task/` | what the agent sees: `TASK.md`, `SPEC.md`, the `oracle` client, and the partials `SPEC.md` is assembled from |
| `docs/` | the reference data the agent gets: species, moves, type chart, and where the reference draws random numbers |
| `harness/` | the grader, the rate limited oracle server, the test set minter, and the generators for `SPEC.md` and `docs/` |
| `sandbox/` | Docker setup: the task container, the oracle container, and an egress proxy that only reaches the Anthropic API |
| `runner/` | the run supervisor, resume, checkpointing, transcript rendering, and grading of every checkpoint |
| `analysis/` | regrading, divergence classification, timelines, and the figures |
| `results/` | per model scores over time and at 120 minutes, timelines, break profiles, and the battles minted under the original rules |
| `tests/` | the grader, the oracle, the grammar in `SPEC.md`, the draw site table, and the choice rules |

The test set (`ps_test.jsonl`) is private so the eval stays usable. Email me if you would like it. Everything that
reads it takes its path from `POKEVAL_TEST_SET`; tests that need it are skipped when it is not set.

## Reproducing

1. `npm install` (installs `pokemon-showdown` 0.11.11, the reference every gold log comes from). Python 3.11 with
   `pytest` and `matplotlib`.
2. `make test` runs the test suite. `make docs` regenerates `docs/`. With the test set, `make sites` refreshes
   `rng_sites.json` and `make spec` regenerates `task/SPEC.md`. `make corpus` mints a new test set.
3. `make box` builds and starts the sandbox (`docker compose` in `sandbox/`).
4. Run a candidate with a Claude Code token (create one with `claude setup-token`):

   ```
   export CLAUDE_CODE_OAUTH_TOKEN=...
   export POKEVAL_TEST_SET=/path/to/ps_test.jsonl
   runner/run.sh <run-name> --model "claude-opus-5[1m]" --hours 2
   ```

   The run lands in `runs/<run-name>/`: transcript, checkpoints every five minutes, oracle queries, score and
   trajectory. `runner/resume.sh <run-name>` continues an interrupted run in the same box.
5. Grade an engine left in the box with `make grade NAME=<run-name>`, or any engine directly:

   ```
   python3 harness/grade.py "$POKEVAL_TEST_SET" 'name=python3 path/to/engine.py'
   ```

   The engine reads `docs/` next to its own file, as it does in `/task`.
6. To rebuild `results/` from your own runs: `python3 analysis/regrade_turn_share.py <finals.json> runs` grades every
   checkpoint, `python3 analysis/export_results.py runs results` writes the per model score files, and
   `python3 analysis/timelines.py runs` writes `results/timelines.json`. `analysis/divergence_causes.py` and
   `analysis/break_profiles.py` produce the break profiles; the first quotes test set lines, so keep its output private.
7. `make figures OUT=figures` redraws the figures from `results/`. The test set figure is drawn only when
   `POKEVAL_TEST_SET` is set.
