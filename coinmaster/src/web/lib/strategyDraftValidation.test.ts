import assert from 'node:assert/strict';
import test from 'node:test';
import { parseFiniteNumberFields } from './strategyDraftValidation';

test('numeric array drafts accept each finite entered value', () => {
  assert.deepEqual(parseFiniteNumberFields(['0.25', ' 1.5 ', '-2']), [0.25, 1.5, -2]);
});

test('numeric array drafts reject blanks and non-finite values without saving partial rows', () => {
  assert.equal(parseFiniteNumberFields(['0.25', '']), null);
  assert.equal(parseFiniteNumberFields(['0.25', 'NaN']), null);
  assert.equal(parseFiniteNumberFields([]), null);
});
