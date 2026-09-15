const {Dex, Teams} = require('pokemon-showdown');

const gen1 = Dex.mod('gen1');
const SPECIES = gen1.species.all().filter(s => s.num >= 1 && s.num <= 151 && !s.forme && s.exists);
const MOVES = gen1.moves.all().filter(m => m.num >= 1 && m.num <= 165 && !m.isNonstandard);
const SPECIES_NAMES = new Set(SPECIES.map(s => s.name));
const MOVE_IDS = new Set(MOVES.map(m => m.id));
const BALANCE = parseFloat(process.env.MOVE_BALANCE || '1.0');

const learnset = (speciesId) => {
  const ls = (gen1.data.Learnsets[speciesId] || {}).learnset || {};
  return Object.keys(ls).filter(m => ls[m].some(src => src.startsWith('1')) && MOVE_IDS.has(m));
};

const LEARNERS = {};
for (const s of SPECIES) for (const m of learnset(s.id)) LEARNERS[m] = (LEARNERS[m] || 0) + 1;

const isAttack = (m) => gen1.moves.get(m).category !== 'Status';
const weight = (m) => Math.pow(LEARNERS[m], -BALANCE);

function shuffle(a, rng) {
  for (let j = a.length - 1; j > 0; j--) {
    const k = Math.floor(rng() * (j + 1));
    [a[j], a[k]] = [a[k], a[j]];
  }
  return a;
}

function weightedOrder(items, rng) {
  const rest = [...items], out = [];
  while (rest.length) {
    const total = rest.reduce((t, m) => t + weight(m), 0);
    let r = rng() * total, i = 0;
    for (; i < rest.length - 1; i++) {
      r -= weight(rest[i]);
      if (r <= 0) break;
    }
    out.push(rest.splice(i, 1)[0]);
  }
  return out;
}

function randomTeam(rng, size = 6) {
  const pool = [...SPECIES], picks = [];
  for (let i = 0; i < size; i++) {
    const species = pool.splice(Math.floor(rng() * pool.length), 1)[0];
    const all = learnset(species.id);
    const attacks = weightedOrder(all.filter(isAttack), rng);
    const chosen = attacks.slice(0, 2);
    const others = weightedOrder([...attacks.slice(2), ...all.filter(m => !isAttack(m))], rng);
    while (chosen.length < 4 && others.length) chosen.push(others.shift());
    picks.push({name: species.name, species: species.name, moves: shuffle(chosen, rng), level: 100, gender: '', ivs: {}, evs: {}});
  }
  return Teams.pack(picks);
}

const toBattleTeam = (packed) => Teams.unpack(packed).map(s => ({...s, ability: 'No Ability'}));

module.exports = {SPECIES, MOVES, SPECIES_NAMES, MOVE_IDS, learnset, randomTeam, toBattleTeam};
