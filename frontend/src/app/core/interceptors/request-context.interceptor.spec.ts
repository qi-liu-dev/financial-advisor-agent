import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { SessionService } from '../auth/session.service';
import { requestContextInterceptor } from './request-context.interceptor';

describe('requestContextInterceptor', () => {
  let client: HttpClient;
  let http: HttpTestingController;
  let session: SessionService;

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([requestContextInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    client = TestBed.inject(HttpClient);
    http = TestBed.inject(HttpTestingController);
    session = TestBed.inject(SessionService);
  });

  afterEach(() => http.verify());

  it('adds a correlation ID and an optional tab-scoped API key to API requests', () => {
    session.setApiKey('synthetic-test-key');
    client.get('/api/v1/health').subscribe();

    const request = http.expectOne('/api/v1/health');
    expect(request.request.headers.get('X-API-Key')).toBe('synthetic-test-key');
    expect(request.request.headers.get('X-Request-ID')).toBeTruthy();
    request.flush({ status: 'ok' });
  });

  it('does not add API headers to unrelated asset requests', () => {
    client.get('/assets/example.json').subscribe();

    const request = http.expectOne('/assets/example.json');
    expect(request.request.headers.has('X-API-Key')).toBe(false);
    expect(request.request.headers.has('X-Request-ID')).toBe(false);
    request.flush({});
  });
});
