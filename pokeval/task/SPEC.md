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

Every graded line has one of the shapes below. Slots: `<mon>` is `p1a: Name` or `p2a: Name`, the active
Pokémon of player 1 or 2; `<species>` is a species name from `docs/species.json`; `<move>` is a move name
from `docs/moves.json`; `<hp>` is `current/max`; `<status>` is one of `par slp frz brn psn tox`; `<stat>` is a
stat id; `<n>` is an integer; `<player>` is `P1` or `P2`; `<type>` is a type, or two joined by `/`. Where a
slot takes only a few values in that shape, they are listed under it. Everything not in angle brackets is
literal text.

**`|move|`**

```
|move|<mon>|<move>|<mon>
|move|<mon>|<move>|<mon>|[from] <move>
|move|<mon>|<move>|<mon>|[miss]
|move|<mon>|<move>||[still]
    <move>: Razor Wind  Fly  Skull Bash  Solar Beam  Dig  Sky Attack
|move|<mon>|<move>|<mon>|[from] <move>|[miss]
    <move> #2: Razor Wind  Sky Attack  Fly  Rage  Dig  Solar Beam  Skull Bash  Petal Dance  Thrash  Metronome  Mirror Move
|move|<mon>|<move>||[from] <move>|[still]
    <move> #1: Sky Attack  Skull Bash
    <move> #2: Mirror Move  Metronome
```

**`|-damage|`**

```
|-damage|<mon>|<hp>
|-damage|<mon>|0 fnt
|-damage|<mon>|<hp> <status>
    <status>: par  psn  slp  brn  frz  tox
|-damage|<mon>|<hp>|[from] Recoil
|-damage|<mon>|<hp> <status>|[from] <status>|[of] <mon>
    <status> #1: psn  brn
    <status> #2: psn  brn
|-damage|<mon>|<hp>|[from] confusion
|-damage|<mon>|<hp> <status>|[from] <status>
    <status> #1: tox  psn  brn
    <status> #2: psn  brn
|-damage|<mon>|0 fnt|[from] Recoil
|-damage|<mon>|0 fnt|[from] <status>|[of] <mon>
    <status>: psn  brn
|-damage|<mon>|<hp>|[from] <move>|[of] <mon>
    <move>: Leech Seed
|-damage|<mon>|0 fnt|[from] confusion
|-damage|<mon>|<hp> <status>|[from] Recoil
    <status>: par  brn  psn  tox
|-damage|<mon>|0 fnt|[from] <status>
    <status>: psn  brn
|-damage|<mon>|0 fnt|[from] <move>|[of] <mon>
    <move>: Leech Seed
|-damage|<mon>|<hp> <status>|[from] confusion
    <status>: par
```

**`|turn|`**

```
|turn|<n>
```

**`|switch|`**

```
|switch|<mon>|<species>|<hp>
|switch|<mon>|<species>|<hp> <status>
    <status>: par  psn  frz  slp  brn  tox
```

**`|faint|`**

```
|faint|<mon>
```

**`|-resisted|`**

```
|-resisted|<mon>
```

**`|-crit|`**

```
|-crit|<mon>
```

**`|-miss|`**

```
|-miss|<mon>
```

**`|-supereffective|`**

```
|-supereffective|<mon>
```

**`|-prepare|`**

```
|-prepare|<mon>|<move>
    <move>: Razor Wind  Fly  Skull Bash  Solar Beam  Dig  Sky Attack
```

**`|-hitcount|`**

```
|-hitcount|<mon>|<n>
```

**`|-immune|`**

```
|-immune|<mon>
|-immune|<mon>|[ohko]
```

**`|cant|`**

```
|cant|<mon>|<status>
    <status>: slp  frz  par
|cant|<mon>|partiallytrapped
|cant|<mon>|recharge
|cant|<mon>|flinch
|cant|<mon>|Disable|<move>
    <move>: Sky Attack  Rage
```

**`|-boost|`**

```
|-boost|<mon>|<stat>|<n>
    <stat>: def  spe  atk  evasion  spa  spd
|-boost|<mon>|<stat>|<n>|[from] <move>
    <move>: Rage
    <stat>: atk
```

**`|-unboost|`**

```
|-unboost|<mon>|<stat>|<n>
    <stat>: spe  def  atk  accuracy  spa  spd
```

**`|-heal|`**

```
|-heal|<mon>|<hp>|[from] drain|[of] <mon>
|-heal|<mon>|<hp> <status>|[silent]
    <status>: slp  par
|-heal|<mon>|<hp>|[silent]
|-heal|<mon>|<hp>
|-heal|<mon>|<hp> <status>|[from] drain|[of] <mon>
    <status>: par  brn  psn
|-heal|<mon>|<hp> <status>
    <status>: par
```

**`|-start|`**

```
|-start|<mon>|<move>
    <move>: Bide  Substitute  Reflect  Mist  Light Screen
|-start|<mon>|confusion|[silent]
|-start|<mon>|confusion
|-start|<mon>|move: <move>
    <move>: Focus Energy  Leech Seed
|-start|<mon>|Mimic|<move>
|-start|<mon>|Disable|<move>
|-start|<mon>|typechange|<type>|[from] move: <move>|[of] <mon>
    <move>: Conversion
    <type>: Water  Normal/Flying  Ground
```

**`|-activate|`**

```
|-activate|<mon>|<move>
    <move>: Bide
|-activate|<mon>|confusion
|-activate|<mon>|<move>|[damage]
    <move>: Substitute
|-activate|<mon>|move: <move>
    <move>: Haze  Mist
```

**`|win|`**

```
|win|<player>
```

**`|-status|`**

```
|-status|<mon>|<status>
    <status>: par  psn  brn  frz  tox
|-status|<mon>|<status>|[from] move: <move>
    <move>: Rest  Sleep Powder  Hypnosis  Spore  Sing  Lovely Kiss
    <status>: slp
|-status|<mon>|<status>|[silent]
    <status>: psn
```

**`|-message|`**

```
|-message|The foe <species> can't be hit while invulnerable!
```

**`|-fail|`**

```
|-fail|<mon>
|-fail|<mon>|<status>
    <status>: par  slp  tox
|-fail|<mon>|move: <move>|[weak]
    <move>: Substitute
|-fail|<mon>|move: <move>
    <move>: Substitute
```

**`|-fieldactivate|`**

```
|-fieldactivate|move: <move>
    <move>: Pay Day
```

**`|-end|`**

```
|-end|<mon>|<move>
    <move>: Bide  Substitute  Disable
|-end|<mon>|confusion
|-end|<mon>|move: <move>|[silent]
    <move>: Focus Energy
```

**`|-mustrecharge|`**

```
|-mustrecharge|<mon>
```

**`|-ohko|`**

```
|-ohko
```

**`|-curestatus|`**

```
|-curestatus|<mon>|<status>|[msg]
    <status>: slp  frz
|-curestatus|<mon>|<status>|[silent]
    <status>: psn
```

**`|-transform|`**

```
|-transform|<mon>|<mon>
```

**`|-clearallboost|`**

```
|-clearallboost|[silent]
```

**`|-nothing|`**

```
|-nothing
```

**`|tie|`**

```
|tie
```

Any line type or shape not listed here does not occur in a graded log.

## Randomness

The battle uses a 64-bit linear congruential generator:

```
x_{n+1} = (a * x_n + c) mod 2^64
a = 0x5D588B656C078965
c = 0x00269EC3
```

Every draw advances the generator once, then takes the upper 32 bits of the new state:
`result = (x >> 32) & 0xFFFFFFFF`.

```
random(n)              = floor(result * n / 2^32)            -> integer in [0, n)
random(from, to)       = floor(result * (to - from) / 2^32) + from
randomChance(num, den) = random(den) < num
sample(list)           = list[random(len)]
shuffle of k elements  = for i in 0 .. k-2: swap element i with element random(i, k)   (k-1 draws)
```

Every place the reference draws, and when, is listed in `docs/README.md`.

---

There may be behavior not captured by this document, and there is a small chance that some of what it states is
not wholly accurate. The reference, as run by the oracle, is the source of truth.
