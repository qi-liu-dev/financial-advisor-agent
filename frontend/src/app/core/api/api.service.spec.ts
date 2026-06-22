import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiService } from './api.service';

describe('ApiService', () => {
  let api: ApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(ApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('uses the versioned task endpoint and agent filter', () => {
    api.getTasks('client_summary').subscribe((tasks) => expect(tasks).toEqual([]));
    const request = http.expectOne(
      (candidate) =>
        candidate.url === '/api/v1/tasks' &&
        candidate.params.get('agent_type') === 'client_summary',
    );
    expect(request.request.method).toBe('GET');
    request.flush([]);
  });

  it('posts asynchronous optimisation requests to the agent route', () => {
    api
      .createOptimisation('meeting_notes', {
        advisor_id: 'demo-advisor',
        max_variants: 2,
        benchmark_limit: 2,
        repetitions: 2,
      })
      .subscribe();
    const request = http.expectOne('/api/v1/optimisations/meeting_notes');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.max_variants).toBe(2);
    request.flush({
      job_id: 'job-1',
      owner_id: 'demo-advisor',
      agent_type: 'meeting_notes',
      status: 'queued',
      progress: 0,
      request: request.request.body,
      result_id: null,
      error_code: null,
      error_message: null,
      created_at: new Date().toISOString(),
      started_at: null,
      completed_at: null,
    });
  });
});
