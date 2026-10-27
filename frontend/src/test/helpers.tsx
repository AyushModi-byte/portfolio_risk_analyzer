import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { vi } from 'vitest';
import { App } from '../App';
import type { Api } from '../api/client';
import { ApiContext } from '../api/context';
import * as fx from './fixtures';

/** An Api whose every method is a spy returning sensible fixtures unless overridden. */
export function makeApi(overrides: Partial<Api> = {}): Api {
  return {
    health: vi.fn().mockResolvedValue(fx.health),
    samples: vi.fn().mockResolvedValue(fx.samples),
    parse: vi.fn().mockResolvedValue(fx.parseOk),
    analyze: vi.fn().mockResolvedValue(fx.analysis),
    insights: vi.fn().mockResolvedValue(fx.insightsLlm),
    chat: vi.fn().mockResolvedValue(fx.chatResult),
    suggestMapping: vi.fn().mockResolvedValue({ mapping: null, source: 'none', error: 'x' }),
    ...overrides,
  };
}

export function renderWithApi(ui: ReactElement, api: Api = makeApi()) {
  return { api, ...render(<ApiContext.Provider value={api}>{ui}</ApiContext.Provider>) };
}

export function renderApp(overrides: Partial<Api> = {}) {
  return renderWithApi(<App />, makeApi(overrides));
}

export function csvFile(name = 'holdings.csv', content = 'Symbol,Qty\nTCS,10\n'): File {
  return new File([content], name, { type: 'text/csv' });
}
