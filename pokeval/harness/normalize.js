const DROP = new Set(['t:', 'split', 'player', 'gametype', 'gen', 'tier', 'rule', 'teamsize', 'start', 'upkeep',
                      '', '-ability', '-hint', 'debug', 'j', 'l', 'c', 'raw', 'bigerror']);

function normalize(log) {
  const out = [];
  for (const line of log) {
    if (!line || !line.startsWith('|')) continue;
    if (DROP.has(line.slice(1).split('|')[0])) continue;
    if (out.length && out[out.length - 1] === line) continue;
    out.push(line);
  }
  return out;
}

module.exports = {normalize};
