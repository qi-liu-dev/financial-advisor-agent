import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { SessionService } from '../auth/session.service';

export const requestContextInterceptor: HttpInterceptorFn = (request, next) => {
  if (!request.url.includes('/api/')) return next(request);

  const session = inject(SessionService);
  const headers: Record<string, string> = {
    'X-Request-ID': globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`,
  };
  if (session.apiKey()) headers['X-API-Key'] = session.apiKey();

  return next(request.clone({ setHeaders: headers }));
};
