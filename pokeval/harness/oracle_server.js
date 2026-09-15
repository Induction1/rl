const fs = require('fs');
const http = require('http');
const {Battle} = require('pokemon-showdown');
const {SPECIES_NAMES, MOVE_IDS, toBattleTeam} = require('./gen1team.js');
const {normalize} = require('./normalize.js');

const args = process.argv.slice(2);
const opt = (flag, dflt) => { const i = args.indexOf(flag); return i > -1 ? args[i + 1] : dflt; };
const HOST = opt('--host', '127.0.0.1');
const PORT = parseInt(opt('--port', '8732'), 10);
const REFILL_PER_MINUTE = parseInt(opt('--refill', '3000'), 10);
const BUCKET = parseInt(opt('--bucket', '5000'), 10);
const MAX_TURNS = parseInt(opt('--max-turns', '100'), 10);
const LOGFILE = opt('--log', 'oracle_queries.jsonl');
const MAX_BODY = 32 * 1024;
const MAX_CHOICES = 400;

let used = 0, requests = 0, tokens = BUCKET, lastRefill = Date.now();

function available() {
  const now = Date.now();
  tokens = Math.min(BUCKET, tokens + (now - lastRefill) / 60000 * REFILL_PER_MINUTE);
  lastRefill = now;
  return Math.floor(tokens);
}

const status = () => ({
  unit: 'turns', available: available(), bucket: BUCKET, refill_per_minute: REFILL_PER_MINUTE, used,
  max_turns_per_query: MAX_TURNS,
});
const record = (entry) => fs.appendFileSync(LOGFILE, JSON.stringify({n: requests, t: new Date().toISOString(), ...entry}) + '\n');

function validate(spec) {
  if (!spec || typeof spec !== 'object' || Array.isArray(spec)) return 'query must be a JSON object';
  for (const k of Object.keys(spec)) if (!['id', 'seed', 'teams', 'choices'].includes(k)) return `unknown field "${k}"`;
  if (typeof spec.seed !== 'string' || !/^\d{1,5},\d{1,5},\d{1,5},\d{1,5}$/.test(spec.seed)
      || spec.seed.split(',').some(x => parseInt(x, 10) > 65535)) return 'seed must be four integers 0..65535, comma-separated';
  if (!spec.teams || typeof spec.teams !== 'object') return 'teams must be an object with p1 and p2';
  for (const side of ['p1', 'p2']) {
    const team = spec.teams[side];
    if (typeof team !== 'string' || !team) return `teams.${side} must be a packed team string`;
    const members = team.split(']');
    if (members.length > 6) return `teams.${side} must have 1 to 6 members`;
    for (const member of members) {
      const f = member.split('|');
      if (f.length !== 12) return `teams.${side}: a member must have exactly 12 fields`;
      if (!SPECIES_NAMES.has(f[0])) return `teams.${side}: unknown species "${f[0]}"`;
      if (f[1] || f[2] || f[3] || f.slice(5).some(Boolean)) return `teams.${side}: only the species and moves fields may be filled`;
      const moves = f[4].split(',');
      if (moves.length > 4 || moves.some(m => !MOVE_IDS.has(m))) return `teams.${side}: moves must be 1 to 4 move ids from docs/moves.json`;
    }
  }
  if (!Array.isArray(spec.choices) || spec.choices.length > MAX_CHOICES) return `choices must be an array (at most ${MAX_CHOICES} entries)`;
  for (const [i, c] of spec.choices.entries()) {
    if (!c || typeof c !== 'object') return `choices[${i}] must be an object`;
    for (const k of Object.keys(c)) if (!['turn', 'p1', 'p2'].includes(k)) return `choices[${i}]: unknown field "${k}"`;
    if (c.turn !== undefined && !Number.isInteger(c.turn)) return `choices[${i}].turn must be an integer`;
    for (const side of ['p1', 'p2']) {
      const v = c[side];
      if (v != null && !(typeof v === 'string' && /^(move [1-4]|switch [1-6])$/.test(v))) {
        return `choices[${i}].${side} must be "move 1".."move 4", "switch 1".."switch 6", or null`;
      }
    }
  }
  return null;
}

function play(spec) {
  const battle = new Battle({formatid: 'gen1customgame', seed: spec.seed, strictChoices: true});
  battle.setPlayer('p1', {name: 'P1', team: toBattleTeam(spec.teams.p1)});
  battle.setPlayer('p2', {name: 'P2', team: toBattleTeam(spec.teams.p2)});
  const result = (extra) => ({
    log: normalize(battle.log),
    turns: battle.ended ? battle.turn : battle.turn - 1,
    ended: battle.ended,
    ...extra,
  });
  for (const [index, choice] of spec.choices.entries()) {
    if (battle.ended) break;
    if (battle.turn > MAX_TURNS) return result({truncated: `query capped at ${MAX_TURNS} turns`});
    try {
      if (choice.p1) battle.choose('p1', choice.p1);
      if (choice.p2) battle.choose('p2', choice.p2);
    } catch (e) {
      return result({rejected: {index, choice, reason: e.message}});
    }
  }
  return result({});
}

function send(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body)});
  res.end(body);
}

function handle(body, tooBig, res) {
  if (available() < 1) return send(res, 429, {error: 'ORACLE RATE LIMIT: no turns available yet', ...status()});
  requests++;
  const charge = (n) => { tokens -= n; used += n; };
  const fail = (error) => {
    charge(1);
    record({raw: body.slice(0, 2000), charged: 1, error});
    send(res, 200, {error, charged: 1, available: available()});
  };
  if (tooBig) return fail(`request larger than ${MAX_BODY} bytes`);
  let spec;
  try { spec = JSON.parse(body); } catch { return fail('bad json'); }
  const why = validate(spec);
  if (why) return fail(`bad query: ${why}`);
  let out;
  try { out = play(spec); } catch (e) { return fail(`reference error: ${e.message}`); }
  const charged = Math.min(Math.max(out.turns, 1), MAX_TURNS, Math.max(1, available()));
  charge(charged);
  record({spec, charged});
  send(res, 200, {...(spec.id !== undefined && {id: spec.id}), ...out, charged, available: available()});
}

http.createServer((req, res) => {
  if (req.method === 'GET') return send(res, 200, status());
  let body = '', tooBig = false;
  req.on('data', chunk => { if (body.length + chunk.length > MAX_BODY) tooBig = true; else body += chunk; });
  req.on('end', () => handle(body, tooBig, res));
}).listen(PORT, HOST, () => console.log(`oracle on ${HOST}:${PORT}, ${REFILL_PER_MINUTE} turns/min, bucket ${BUCKET}, ${MAX_TURNS}/query`));

for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => process.exit(0));
