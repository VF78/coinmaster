import { JSONFilePreset } from 'lowdb/node';
import { DBShape } from './types.js';

const defaultData: DBShape = {
  positions: [],
  tradeLogs: [],
  biasCommands: [],
  marketTicks: []
};

export async function getDb(file = 'data/db.json') {
  return JSONFilePreset<DBShape>(file, defaultData);
}
