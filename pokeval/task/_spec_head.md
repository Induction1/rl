# Gen 1 Pokémon battle engine

What your engine reads and writes, and the random number generator. The task is in `TASK.md`; the reference's
data and its random draw sites are in `docs/README.md`.

## Input

One JSON object per line on stdin:

```json
{"id": "ps-000001",
 "seed": "1,18,42,58",
 "teams": {"p1": "<packed team>", "p2": "<packed team>"},
 "choices": [{"turn": 1, "p1": "move 3", "p2": "move 3"}, {"turn": 1, "p1": "switch 2", "p2": null}, ...]}
```

**Seed.** Four 16-bit values, most significant first: `"1,18,42,58"` means the generator starts from
`x0 = (1 << 48) | (18 << 32) | (42 << 16) | 58`. Every case has its own seed.

**Teams.** Team members are separated by `]`. Each member is twelve fields separated by `|`: the first is the
species name, the fifth is the comma-separated list of one to four move ids from `docs/moves.json`, and every
other field is empty. All Pokémon are level 100 with the reference's default stats.

**Choices.** In submission order. Each entry has the turn it was submitted in and one string per side. `move N`
uses the Nth move in the active Pokémon's current move list. `switch N` brings in the Nth Pokémon in the side's
current order. `null` means that side had no decision to make at that point.

- After a switch, the Pokémon that came in occupies slot 1 and the one that went out occupies the slot the
  incoming Pokémon came from.
- Mimic replaces its own slot with the copied move; Transform replaces all slots with the target's moves.
- While the engine has locked a Pokémon into a move (for example Rage, Thrash, Petal Dance, or the second turn
  of a two-turn move), the recorded choice is `move 1` whatever slot that move is in, and the locked move
  executes.
- While a Pokémon is holding a partial-trapping move (Bind, Clamp, Fire Spin, Wrap), the recorded choice on the
  following turns may name any slot, and the engine repeats the trapping move regardless.

When such locks begin and end is Generation 1 behavior, which the reference can be queried for.

## Output

One JSON object per line on stdout:

```json
{"id": "ps-000001", "log": ["|switch|p1a: Exeggutor|Exeggutor|330/330", "|turn|1", ...]}
```

`id` is copied from the input. `log` is the ordered list of graded lines your engine produces. Do not emit any
other line type, and do not emit blank lines. In the reference's graded log, consecutive identical lines are
collapsed to one.

### Graded lines

@@LINES@@
