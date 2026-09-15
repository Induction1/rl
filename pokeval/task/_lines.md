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
