const fs = require('fs');
const {Battle, Teams} = require('pokemon-showdown');
const {SPECIES, learnset, toBattleTeam} = require('../harness/gen1team.js');
const {mulberry, randomUint32, randomBattleSeed, bench, pick} = require('../harness/mint.js');

const MAX_TURNS = 1000;

function team(rng) {
  const pool = [...SPECIES], picks = [];
  for (let i = 0; i < 6; i++) {
    const species = pool.splice(Math.floor(rng() * pool.length), 1)[0], all = learnset(species.id), moves = [];
    while (moves.length < 4 && all.length) moves.push(all.splice(Math.floor(rng() * all.length), 1)[0]);
    picks.push({name: species.name, species: species.name, moves, level: 100, gender: '', ivs: {}, evs: {}});
  }
  return Teams.pack(picks);
}

function choose(req, rng) {
  if (!req) return null;
  if (req.forceSwitch) {
    const options = bench(req);
    return options.length ? `switch ${pick(options, rng)}` : null;
  }
  if (!req.active) return null;
  const legal = req.active[0].moves
    .map((m, i) => ({slot: i + 1, disabled: m.disabled, pp: m.pp}))
    .filter(m => !m.disabled && m.pp !== 0);
  return legal.length ? `move ${pick(legal, rng).slot}` : 'move 1';
}

function mintBattle() {
  const rng = mulberry(randomUint32());
  const seed = randomBattleSeed();
  const teams = {p1: team(rng), p2: team(rng)};
  const battle = new Battle({formatid: 'gen1customgame', seed, strictChoices: true});
  battle.setPlayer('p1', {name: 'P1', team: toBattleTeam(teams.p1)});
  battle.setPlayer('p2', {name: 'P2', team: toBattleTeam(teams.p2)});
  for (let guard = 0; !battle.ended && battle.turn <= MAX_TURNS && guard < 4 * MAX_TURNS; guard++) {
    const c1 = choose(battle.p1.activeRequest, rng), c2 = choose(battle.p2.activeRequest, rng);
    if (!c1 && !c2) break;
    if (c1) battle.choose('p1', c1);
    if (c2) battle.choose('p2', c2);
  }
  return {seed, teams, turns: battle.ended ? battle.turn : battle.turn - 1, ended: battle.ended};
}

const [n, out] = [parseInt(process.argv[2] || '1000', 10), process.argv[3]];
if (!out) {
  console.error('usage: node analysis/mint_original_rules.js <n> <out.jsonl>');
  process.exit(1);
}
const rows = Array.from({length: n}, mintBattle);
fs.writeFileSync(out, rows.map(r => JSON.stringify(r)).join('\n') + '\n');
const t = rows.map(r => r.turns).sort((a, b) => a - b);
console.log(`battles ${n} | median ${t[Math.floor(n / 2)]} | p90 ${t[Math.floor(0.9 * n)]} | max ${t[n - 1]} | unfinished ${rows.filter(r => !r.ended).length}`);
