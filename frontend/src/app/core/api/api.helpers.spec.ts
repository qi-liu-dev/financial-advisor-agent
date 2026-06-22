import { mean, qualityScore } from './api.helpers';

const metric = (score: number) => ({ score, feedback: 'Synthetic test feedback.' });

describe('API helpers', () => {
  it('calculates means safely', () => {
    expect(mean([])).toBe(0);
    expect(mean([2, 4])).toBe(3);
  });

  it('calculates quality from the five quality dimensions', () => {
    expect(
      qualityScore({
        faithfulness: metric(5),
        completeness: metric(4),
        risk_awareness: metric(3),
        clarity: metric(4),
        advisor_usefulness: metric(4),
        safety: metric(5),
        format_correctness: metric(5),
        latency_ms: 100,
        estimated_cost: 0.01,
        feedback: 'Synthetic evaluation.',
      }),
    ).toBe(4);
  });
});
