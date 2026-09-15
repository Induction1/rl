const fs = require('fs');
const path = require('path');
const {Battle} = require('pokemon-showdown');
const {toBattleTeam} = require('./gen1team.js');
const {normalize} = require('./normalize.js');

const PS = path.dirname(require.resolve('pokemon-showdown'));
const WRAPPERS = /^Battle\.(random|randomChance|sample|shuffle)$/;
const sources = new Map();
const codeLine = (file, line) => {
  if (!sources.has(file)) sources.set(file, fs.existsSync(file) ? fs.readFileSync(file, 'utf8').split('\n') : []);
  return (sources.get(file)[line - 1] || '').trim();
};

function callSite() {
  let site = null;
  for (const frame of new Error().stack.split('\n').slice(1)) {
    if (frame.includes('prng.js') || frame.includes('rng_sites.js')) continue;
    const m = frame.match(/at (?:(.+?) \()?(.+?):(\d+):(\d+)\)?$/);
    if (!m || WRAPPERS.test(m[1] || '')) continue;
    const fr = {fn: m[1] || '?', file: m[2], line: parseInt(m[3], 10)};
    if (!site) {
      site = fr;
      if (fr.fn !== 'Battle.speedSort') return fr;
      continue;
    }
    return {...site, fn: `${site.fn} <- ${fr.fn}:${fr.line}`};
  }
  return site;
}

const sites = new Map();
let currentBattle = null, inside = false;

function record(kind, args) {
  const {fn, file, line} = callSite();
  const key = `${path.relative(PS, file)}:${line}` + (fn.includes('<-') ? ` (${fn.split('<- ')[1]})` : '');
  if (!sites.has(key)) sites.set(key, {key, fn, kind, args: new Map(), count: 0, battles: new Set(), code: codeLine(file, line)});
  const s = sites.get(key);
  s.count++;
  s.battles.add(currentBattle);
  const sig = JSON.stringify(args);
  s.args.set(sig, (s.args.get(sig) || 0) + 1);
}

function instrument(prng) {
  for (const kind of ['random', 'randomChance', 'sample', 'shuffle']) {
    const original = prng[kind].bind(prng);
    prng[kind] = (...a) => {
      if (inside) return original(...a);
      inside = true;
      try {
        const shown = kind === 'sample' ? [`sample of ${a[0].length}`]
                    : kind === 'shuffle' ? [`shuffle of ${(a[2] === undefined ? a[0].length : a[2]) - (a[1] || 0)}`]
                    : a.map(x => x === undefined ? 'undefined' : x);
        record(kind, shown);
        return original(...a);
      } finally {
        inside = false;
      }
    };
  }
}

function replay(c) {
  currentBattle = c.id;
  const battle = new Battle({formatid: 'gen1customgame', seed: c.seed, strictChoices: true});
  instrument(battle.prng);
  battle.setPlayer('p1', {name: 'P1', team: toBattleTeam(c.teams.p1)});
  battle.setPlayer('p2', {name: 'P2', team: toBattleTeam(c.teams.p2)});
  for (const ch of c.choices) {
    if (battle.ended) break;
    if (ch.p1) battle.choose('p1', ch.p1);
    if (ch.p2) battle.choose('p2', ch.p2);
  }
  return JSON.stringify(normalize(battle.log)) === JSON.stringify(c.gold_log);
}

const src = process.argv[2] || process.env.POKEVAL_TEST_SET;
if (!src) {
  console.error('usage: node harness/rng_sites.js <test set> [N], or set POKEVAL_TEST_SET');
  process.exit(1);
}
const n = parseInt(process.argv[3] || '1000', 10);
const cases = fs.readFileSync(src, 'utf8').split('\n').filter(Boolean).map(l => JSON.parse(l)).slice(0, n);
const unfaithful = cases.filter(c => !replay(c)).map(c => c.id);
const out = [...sites.values()].sort((a, b) => b.count - a.count).map(s => ({
  site: s.key, fn: s.fn, kind: s.kind, code: s.code, count: s.count, battles: s.battles.size,
  args: [...s.args.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6).map(([sig, k]) => ({args: JSON.parse(sig), n: k})),
  distinct_arg_patterns: s.args.size,
}));
process.stderr.write(`replayed ${cases.length}: ${cases.length - unfaithful.length} faithful${unfaithful.length ? `, NOT: ${unfaithful.slice(0, 5)}` : ''}; ${out.length} draw sites\n`);
console.log(JSON.stringify({battles: cases.length, faithful: cases.length - unfaithful.length, sites: out}, null, 1));
