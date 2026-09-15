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
