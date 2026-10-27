import { ApiError, createApi } from './client';
import * as fx from '../test/fixtures';

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json', ...(init.headers as Record<string, string>) },
    status: init.status ?? 200,
    statusText: init.statusText,
  });
}

describe('api client', () => {
  it('builds URLs from the base URL, tolerating a trailing slash', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(fx.health));
    await createApi('http://api.test/', fetchImpl).health();
    expect(fetchImpl).toHaveBeenCalledWith('http://api.test/health', expect.anything());
  });

  it('posts JSON for analyze, insights, chat and mapping suggestions', async () => {
    const fetchImpl = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({})));
    const api = createApi('http://api.test', fetchImpl);

    await api.analyze({ holdings: fx.parseOk.holdings, base_currency: 'USD', benchmark: '^GSPC' });
    await api.insights(fx.analysis);
    await api.chat({
      analysis: fx.analysis,
      messages: [{ role: 'user', content: 'hi' }],
      request: null,
    });
    await api.suggestMapping(['a'], [{ a: '1' }]);

    const calls = fetchImpl.mock.calls as [string, RequestInit][];
    expect(calls.map(([url]) => url)).toEqual([
      'http://api.test/api/analyze',
      'http://api.test/api/insights',
      'http://api.test/api/chat',
      'http://api.test/api/mapping/suggest',
    ]);
    for (const [, init] of calls) {
      expect(init.method).toBe('POST');
      expect(init.headers).toEqual({ 'Content-Type': 'application/json' });
    }
    expect(JSON.parse(calls[0]?.[1].body as string)).toEqual({
      holdings: fx.parseOk.holdings,
      base_currency: 'USD',
      benchmark: '^GSPC',
    });
    expect(JSON.parse(calls[3]?.[1].body as string)).toEqual({
      headers: ['a'],
      sample_rows: [{ a: '1' }],
    });
  });

  it('uploads the file and optional mapping as multipart form data', async () => {
    const fetchImpl = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(fx.parseOk)));
    const api = createApi('http://api.test', fetchImpl);
    const file = new File(['a,b'], 'h.csv');

    await api.parse(file);
    await api.parse(file, { symbol: 'S', quantity: 'Q' });

    const [first, second] = (fetchImpl.mock.calls as [string, RequestInit][]).map(
      ([, init]) => init.body as FormData,
    );
    expect(first?.get('file')).toBeInstanceOf(File);
    expect(first?.has('mapping')).toBe(false);
    expect(JSON.parse(second?.get('mapping') as string)).toEqual({ symbol: 'S', quantity: 'Q' });
  });

  it('turns the backend error shape into an ApiError with a Retry-After', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(
          { error: 'rate_limited', detail: 'Too many AI requests.' },
          { status: 429, headers: { 'Retry-After': '42' } },
        ),
      );
    const error = await createApi('http://api.test', fetchImpl)
      .health()
      .catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 429,
      code: 'rate_limited',
      message: 'Too many AI requests.',
      retryAfter: 42,
    });
  });

  it('handles a non-JSON error page', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        new Response('<html>Bad gateway</html>', { status: 502, statusText: 'Bad Gateway' }),
      );
    const error = await createApi('http://api.test', fetchImpl)
      .health()
      .catch((e: unknown) => e);
    expect(error).toMatchObject({
      status: 502,
      code: 'error',
      message: 'Bad Gateway',
      retryAfter: null,
    });
  });

  it('reports an unreachable server as a network error', async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    const error = await createApi('http://api.test', fetchImpl)
      .health()
      .catch((e: unknown) => e);
    expect(error).toMatchObject({ status: 0, code: 'network_error' });
  });

  it('lets an aborted request through unchanged', async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new DOMException('aborted', 'AbortError'));
    const error = await createApi('http://api.test', fetchImpl)
      .health()
      .catch((e: unknown) => e);
    expect(error).toBeInstanceOf(DOMException);
  });
});

describe('configuration', () => {
  it('reads the API URL from VITE_API_URL only', async () => {
    vi.stubEnv('VITE_API_URL', ' http://configured.test ');
    const { apiBaseUrl } = await import('./client');
    expect(apiBaseUrl()).toBe('http://configured.test');
    vi.stubEnv('VITE_API_URL', '');
    expect(apiBaseUrl()).toBeNull();
    vi.unstubAllEnvs();
  });

  it('has no hard-coded backend URL in the source', () => {
    const sources = import.meta.glob<string>(
      ['/src/**/*.ts', '/src/**/*.tsx', '!/src/**/*.test.*', '!/src/test/**'],
      {
        query: '?raw',
        import: 'default',
        eager: true,
      },
    );
    expect(Object.keys(sources).length).toBeGreaterThan(20);
    for (const [path, text] of Object.entries(sources)) {
      expect(text, path).not.toMatch(
        /https?:\/\/(localhost|127\.0\.0\.1|[\w.-]*\.(hf\.space|vercel\.app))/,
      );
    }
  });
});
