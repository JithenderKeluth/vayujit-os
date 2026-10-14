import { CommerceJourneySummaryComponent } from './commerce-journey-summary.component';
import type { CommerceJourney } from './commerce-journey.types';

const journey: CommerceJourney = {
  id: 'journey-1',
  goal_id: 'goal-1',
  status: 'IN_PROGRESS',
  stages: [],
  completed_stage_count: 1,
  total_stage_count: 8,
  next_action: {
    code: 'REVIEW_RESEARCH',
    title: 'Review product opportunities',
    detail: 'Review the current evidence.',
    route: '/intelligence/product-opportunities',
    human_controlled: true,
  },
  counts: {},
  context: {
    confirmed: true,
    values: {
      category: 'kids',
      marketplace: 'AMAZON_IN',
      budget: 300000,
      currency: 'INR',
    },
  },
  context_confirmation: { required: false, source: 'USER_CONFIRMED' },
  remaining_requirements: [],
  human_controlled: true,
};

describe('CommerceJourneySummaryComponent', () => {
  it('projects seller goal context without creating a second authority', () => {
    const component = new CommerceJourneySummaryComponent();
    expect(component.contextFacts(journey)).toEqual([
      { label: 'Category', value: 'kids' },
      { label: 'Marketplace', value: 'AMAZON_IN' },
      { label: 'Budget', value: '300000' },
      { label: 'Currency', value: 'INR' },
    ]);
  });
});
