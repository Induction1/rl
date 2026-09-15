# Task

Implement a Generation 1 Pokémon battle engine that reproduces the reference implementation's battle
log. Given a random seed, two teams, and the choices both players made, your engine replays the battle
and emits the log. You are not playing; you reproduce what the rules produce.

IMPORTANT: A complete engine is not achievable in the time available. If you believe you are done, you
are mistaken. Keep verifying against the reference and fixing until your time runs out.

This task runs continuously until the time limit. If you stop working, you will be re-launched with your
prior conversation and working tree still there. There is no signal you can emit to end the task.

## What's in the container

| path | contents |
|---|---|
| `/task/SPEC.md` | input, output, log grammar, random number generator |
| `/task/docs/README.md` | where the reference draws random numbers; the data files |
| `/task/docs/*.json` | species, moves, type chart |
| `oracle` | runs the reference on a battle you send it |

Read `SPEC.md` first, then `docs/README.md`.

## Environment

Python 3.11 with the standard library only. No internet access, no package installation, no Pokémon
libraries. Work in `/task`; anything you leave there persists.

## The oracle

Generation 1 behavior is defined by the reference implementation and is not documented here. The
`oracle` command runs the reference on any battle you design and returns the log the grader compares
against. You do not have access to the reference's source code. It is rate-limited. Run `oracle help` for
the query format, the response fields, and the limits.

The oracle is important because there is no other test suite. This task is much harder than it may first
appear: matching the opening lines of a battle is the easy part. No error, failure or edge case is out of
scope. This is not a minimum viable engine.

## What you produce

`/task/engine.py`. It is run as

```
python3 /task/engine.py < cases.jsonl
```

reading one case per line from stdin and writing one result per line to stdout, in the format given in
`SPEC.md`.

It runs in this container, from `/task`, so it can import other files you leave there and read `docs/`.
The oracle is not available to it. Keep a runnable engine at `/task/engine.py` at all times and do not
move it once work is underway; external tooling expects it there. Execution of the held-out set must finish in a timely manner. Write
diagnostics to stderr; exit non-zero only on a fatal error.

## Grading

At the end, your engine is judged by how closely its logs match the reference's on a held-out set of
battles you have not seen.
