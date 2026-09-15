const fs = require('fs');
const {Dex} = require('pokemon-showdown');
const {SPECIES, MOVES} = require('./gen1team.js');

const TYPES = ['Normal', 'Fighting', 'Flying', 'Poison', 'Ground', 'Rock', 'Bug', 'Ghost',
               'Fire', 'Water', 'Grass', 'Electric', 'Psychic', 'Ice', 'Dragon'];
const gen1 = Dex.mod('gen1');
const present = (obj) => Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined && v !== false && v !== null));

const species = Object.fromEntries(SPECIES.map(s => [s.id, {
  name: s.name, num: s.num, types: s.types,
  baseStats: {hp: s.baseStats.hp, atk: s.baseStats.atk, def: s.baseStats.def, spa: s.baseStats.spa, spe: s.baseStats.spe},
}]));

const moves = Object.fromEntries(MOVES.map(m => [m.id, present({
  name: m.name, num: m.num, type: m.type, category: m.category, basePower: m.basePower, accuracy: m.accuracy,
  pp: m.pp, priority: m.priority, target: m.target,
  critRatio: m.critRatio && m.critRatio !== 1 ? m.critRatio : undefined,
  drain: m.drain, recoil: m.recoil, multihit: m.multihit, status: m.status, volatileStatus: m.volatileStatus,
  boosts: m.boosts,
  secondary: m.secondary && {chance: m.secondary.chance, status: m.secondary.status || null, boosts: m.secondary.boosts || null},
  twoTurn: m.flags?.charge ? true : undefined,
  selfVolatile: m.self?.volatileStatus,
  damage: m.damage,
  damageCallback: m.damageCallback ? true : undefined,
  ohko: m.ohko ? true : undefined,
  selfdestruct: m.selfdestruct,
  ignoreImmunity: m.ignoreImmunity,
  hasCrashDamage: m.hasCrashDamage ? true : undefined,
})]));

const typechart = Object.fromEntries(TYPES.map(atk => [atk, Object.fromEntries(TYPES.map(def => {
  const eff = gen1.getEffectiveness(atk, def);
  return [def, gen1.getImmunity(atk, def) ? (eff > 0 ? 2 : eff < 0 ? 0.5 : 1) : 0];
}))]));

const write = (name, data) => fs.writeFileSync(`docs/${name}.json`, JSON.stringify(data, null, 1) + '\n');
write('species', species);
write('moves', moves);
write('typechart', typechart);
console.log(`docs: ${Object.keys(species).length} species, ${Object.keys(moves).length} moves, ${TYPES.length}x${TYPES.length} type chart`);
