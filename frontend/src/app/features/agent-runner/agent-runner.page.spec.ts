import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { BenchmarkTaskResponse, PromptVersionPage } from '../../core/api/api.models';
import { AgentRunnerPage } from './agent-runner.page';

const page = (agent: 'client_summary' | 'meeting_notes'): PromptVersionPage => ({
  items: [
    {
      agent_type: agent,
      version: 'baseline',
      prompt: 'Synthetic prompt.',
      parent_version: null,
      reflection: null,
      average_scores: null,
      status: 'baseline',
      is_active: true,
      selected_at: null,
      activated_at: null,
      created_at: '2026-06-22T12:00:00Z',
    },
  ],
  page: { page: 1, page_size: 200, total_items: 1, total_pages: 1 },
});

const tasks: BenchmarkTaskResponse[] = [
  {
    task_id: 'summary-1',
    agent_type: 'client_summary',
    difficulty: 'easy',
    tags: ['retirement'],
    payload: {
      client_profile: {
        client_id: 'client-1',
        risk_tolerance: 'balanced',
        goals: ['Retire'],
        constraints: [],
      },
      portfolio_summary: {
        portfolio_id: 'portfolio-1',
        asset_allocation: { equities: 60, bonds: 40 },
        risk_notes: [],
      },
    },
    expected: { must_mention: [], must_not_mention: [], required_citations: [] },
  },
  {
    task_id: 'meeting-1',
    agent_type: 'meeting_notes',
    difficulty: 'medium',
    tags: ['follow-up'],
    payload: {
      meeting_id: 'meeting-1',
      client_id: 'client-1',
      transcript: [{ turn_id: '1', speaker: 'Client', text: 'I am worried about risk.' }],
    },
    expected: { must_mention: [], must_not_mention: [], required_citations: [] },
  },
];

const memory = {
  advisor_id: 'demo-advisor',
  preferences: {
    summary_style: 'brief' as const,
    detail_level: 'high' as const,
    risk_focus: 'high' as const,
    preferred_language: 'en',
  },
  created_at: '2026-06-22T12:00:00Z',
  updated_at: '2026-06-23T12:00:00Z',
};

describe('AgentRunnerPage', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    localStorage.clear();
    sessionStorage.clear();
    await TestBed.configureTestingModule({
      imports: [AgentRunnerPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('updates task and prompt selections when the agent form control changes', () => {
    const fixture = TestBed.createComponent(AgentRunnerPage);
    const component = fixture.componentInstance;

    http
      .expectOne(
        (request) =>
          request.url === '/api/v1/prompt-versions/client_summary' &&
          request.params.get('page_size') === '200',
      )
      .flush(page('client_summary'));
    http.expectOne('/api/v1/memory/demo-advisor').flush(memory);
    http.expectOne('/api/v1/tasks').flush(tasks);
    fixture.detectChanges();

    expect(component.form.controls.summaryStyle.value).toBe('brief');
    expect(component.form.controls.detailLevel.value).toBe('high');
    expect(component.form.controls.riskFocus.value).toBe('high');
    expect(component.form.controls.preferredLanguage.value).toBe('en');
    expect(component.matchingTasks().map((task) => task.task_id)).toEqual(['summary-1']);
    expect(component.selectedTask()?.task_id).toBe('summary-1');
    expect(component.selectedPrompt()).toBeNull();
    component.form.controls.promptVersion.setValue('baseline');
    expect(component.selectedPrompt()?.agent_type).toBe('client_summary');

    component.form.controls.agentType.setValue('meeting_notes');
    http
      .expectOne('/api/v1/prompt-versions/meeting_notes?page=1&page_size=200')
      .flush(page('meeting_notes'));
    fixture.detectChanges();

    expect(component.matchingTasks().map((task) => task.task_id)).toEqual(['meeting-1']);
    expect(component.selectedTask()?.task_id).toBe('meeting-1');
    expect(component.selectedPrompt()?.agent_type).toBe('meeting_notes');
  });
});
