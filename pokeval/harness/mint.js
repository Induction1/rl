const crypto = require('crypto');
const fs = require('fs');
const {Battle, Dex} = require('pokemon-showdown');
const {randomTeam, toBattleTeam} = require('./gen1team.js');
const {normalize} = require('./normalize.js');

const gen1 = Dex.mod('gen1');
const ATTACK_P = 0.75;
const SWITCH_P = 1 / 40;

function mulberry(a) {
  return () => {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

const randomUint32 = () => crypto.randomBytes(4).readUInt32LE(0);
const randomBattleSeed = () => Array.from({length: 4}, () => crypto.randomBytes(2).readUInt16LE(0)).join(',');
const bench = (req) => req.side.pokemon.flatMap((p, i) => (!p.active && p.condition !== '0 fnt') ? [i + 1] : []);
const pick = (list, rng) => list[Math.floor(rng() * list.length)];

function choose(req, rng) {
  if (!req) return null;
  if (req.forceSwitch) {
    const options = bench(req);
    return options.length ? `switch ${pick(options, rng)}` : null;
  }
  if (!req.active) return null;
  if (!req.active[0].trapped && rng() < SWITCH_P) {
    const options = bench(req);
    if (options.length) return `switch ${pick(options, rng)}`;
  }
  const legal = req.active[0].moves
    .map((m, i) => ({slot: i + 1, id: m.id, disabled: m.disabled, pp: m.pp}))
    .filter(m => !m.disabled && m.pp !== 0);
  if (!legal.length) return 'move 1';
  const attacks = legal.filter(m => gen1.moves.get(m.id).category !== 'Status');
  const pool = (attacks.length && rng() < ATTACK_P) ? attacks : legal;
  return `move ${pick(pool, rng).slot}`;
}

function mintOne(caseNum, maxTurns, constructionSeed = randomUint32()) {
  const rng = mulberry(constructionSeed);
  const seed = randomBattleSeed();
  const teams = {p1: randomTeam(rng), p2: randomTeam(rng)};
  const battle = new Battle({formatid: 'gen1customgame', seed, strictChoices: true});
  battle.setPlayer('p1', {name: 'P1', team: toBattleTeam(teams.p1)});
  battle.setPlayer('p2', {name: 'P2', team: toBattleTeam(teams.p2)});
  const choices = [];
  for (let guard = 0; !battle.ended && battle.turn <= maxTurns && guard < 2000; guard++) {
    const c1 = choose(battle.p1.activeRequest, rng), c2 = choose(battle.p2.activeRequest, rng);
    if (!c1 && !c2) break;
    const turn = battle.turn;
    if (c1) battle.choose('p1', c1);
    if (c2) battle.choose('p2', c2);
    choices.push({turn, p1: c1, p2: c2});
  }
  return {
    id: `ps-${String(caseNum).padStart(6, '0')}`,
    seed, teams, choices,
    gold_log: normalize(battle.log),
    final_seed: battle.prng.getSeed(),
    turns: battle.ended ? battle.turn : battle.turn - 1,
    ended: battle.ended,
  };
}

function mintCorpus(n, maxTurns) {
  const out = [];
  let dropped = 0;
  while (out.length < n) {
    const c = mintOne(out.length + 1, maxTurns);
    if (c.ended && c.gold_log.length >= 6) out.push(c); else dropped++;
  }
  return {cases: out, dropped};
}

function summary(cases) {
  const turns = cases.map(c => c.turns).sort((a, b) => a - b);
  const q = (p) => turns[Math.min(turns.length - 1, Math.floor(p * turns.length))];
  return `cases ${cases.length} | turns min ${turns[0]} median ${q(0.5)} p90 ${q(0.9)} p99 ${q(0.99)} max ${turns[turns.length - 1]}`;
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const opt = (flag, dflt) => { const i = args.indexOf(flag); return i > -1 ? args[i + 1] : dflt; };
  const n = parseInt(opt('--n', '1000'), 10), cap = parseInt(opt('--cap', '100'), 10), out = opt('--out', 'ps_test.jsonl');
  if (fs.existsSync(out) && !args.includes('--force')) {
    console.error(`${out} exists; a re-mint is a NEW held-out set. Pass --force to overwrite.`);
    process.exit(1);
  }
  const {cases, dropped} = mintCorpus(n, cap);
  fs.writeFileSync(out, cases.map(c => JSON.stringify(c)).join('\n') + '\n');
  console.log(`${summary(cases)} | dropped ${dropped} at the ${cap}-turn cap -> ${out}`);
}

module.exports = {mintOne, mintCorpus, summary, mulberry, randomUint32, randomBattleSeed, bench, pick};
