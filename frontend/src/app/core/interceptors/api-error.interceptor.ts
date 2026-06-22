import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { ApiErrorBody } from '../api/api.models';
import { ToastService } from '../services/toast.service';

export const apiErrorInterceptor: HttpInterceptorFn = (request, next) => {
  const toasts = inject(ToastService);
  return next(request).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && !request.url.endsWith('/health')) {
        const message = extractMessage(error);
        const requestId = error.headers.get('X-Request-ID');
        toasts.error(
          `${error.status || 'Network'} error`,
          requestId ? `${message} · Request ${requestId}` : message,
        );
      }
      return throwError(() => error);
    }),
  );
};

function extractMessage(error: HttpErrorResponse): string {
  const body = error.error as ApiErrorBody | string | null;
  if (typeof body === 'string' && body.trim()) return body;
  const detail = body && typeof body === 'object' ? body.detail : undefined;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return (
      detail
        .map((item) => item.msg)
        .filter(Boolean)
        .join('; ') || 'Validation failed.'
    );
  }
  if (detail && typeof detail === 'object' && detail.message) return detail.message;
  return error.message || 'The request could not be completed.';
}
