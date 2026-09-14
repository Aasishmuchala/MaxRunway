import test from 'node:test';
import assert from 'node:assert/strict';
import {samplePlan, validateReview} from '../analysis.mjs';

const goodReview = () => ({
  visualVerdict: 'changed',
  scores: {geometry: 85, materials: 70, lighting: 90, colour: 88, motionContinuity: 82},
  findings: ['Stone texture changed.'], summary: 'Visible drift remains.',
});

test('review accepts only complete bounded scores', () => {
  assert.equal(validateReview(goodReview()).scores.materials, 70);
  const invalid = goodReview();
  invalid.scores.materials = 101;
  assert.throws(() => validateReview(invalid), /invalid score/);
});

test('review does not accept a provider invented perfect verdict', () => {
  const invalid = goodReview();
  invalid.visualVerdict = 'perfect';
  assert.throws(() => validateReview(invalid), /invalid visual verdict/);
});

test('sample plan spans the whole shot and maps native frames', () => {
  const frames = Array.from({length: 241}, (_, index) => ({preview: `frame_${index}.png`}));
  const plan = samplePlan({mode: 'video', fps: 24, frames}, 10.041667);
  assert.equal(plan.length, 4);
  assert.equal(plan[0].native, 'frame_0.png');
  assert.equal(plan.at(-1).native, 'frame_240.png');
  assert.ok(plan.at(-1).seconds < 10.041667);
});

test('still source stays fixed while generated video is sampled', () => {
  const plan = samplePlan({mode: 'image', fps: 24, frames: [{preview: 'anchor.png'}]}, 5);
  assert.ok(plan.every(item => item.native === 'anchor.png'));
  assert.ok(plan.at(-1).seconds > plan[0].seconds);
});
