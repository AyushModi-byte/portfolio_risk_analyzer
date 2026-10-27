import { useCallback, useEffect, useRef, useState } from 'react';
import type { Api } from '../api/client';
import type {
  AnalysisResult,
  AnalyzeRequest,
  ColumnMapping,
  Currency,
  Holding,
  InsightsResult,
  ParseResponse,
  SampleInfo,
} from '../api/types';
import { friendlyError, type FriendlyError } from '../lib/errors';
import { validateFile } from '../lib/files';

export type Phase = 'upload' | 'parsing' | 'mapping' | 'review' | 'analyzing' | 'dashboard';

export type InsightsState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; result: InsightsResult }
  | { status: 'error'; error: FriendlyError };

export interface FlowState {
  phase: Phase;
  file: File | null;
  parse: ParseResponse | null;
  request: AnalyzeRequest | null;
  analysis: AnalysisResult | null;
  /** A re-analysis (currency or benchmark change) is running; the old result stays visible. */
  reloading: boolean;
  insights: InsightsState;
  error: FriendlyError | null;
  mappingError: string | null;
  notice: string | null;
}

const INITIAL: FlowState = {
  phase: 'upload',
  file: null,
  parse: null,
  request: null,
  analysis: null,
  reloading: false,
  insights: { status: 'idle' },
  error: null,
  mappingError: null,
  notice: null,
};

const US_EXCHANGES = new Set(['NASDAQ', 'NYSE', 'AMEX', 'US']);

/** A starting base currency for an uploaded file: USD when most holdings are US-listed. */
export function guessBaseCurrency(holdings: Holding[]): Currency {
  const us = holdings.filter(
    (h) =>
      h.currency?.toUpperCase() === 'USD' || US_EXCHANGES.has((h.exchange ?? '').toUpperCase()),
  ).length;
  return us > holdings.length / 2 ? 'USD' : 'INR';
}

export interface FlowActions {
  uploadFile: (file: File) => void;
  loadSample: (name: string) => void;
  confirmMapping: (mapping: ColumnMapping) => void;
  resolveSymbols: (fixes: Record<string, string | null>) => void;
  changeControls: (change: { base_currency?: Currency; benchmark?: string | null }) => void;
  retryInsights: () => void;
  retry: () => void;
  dismissError: () => void;
  reset: () => void;
}

export function useFlow(api: Api): { state: FlowState; actions: FlowActions } {
  const [state, setState] = useState<FlowState>(INITIAL);
  const latest = useRef(state);
  const runId = useRef(0);
  const samples = useRef<SampleInfo[] | null>(null);
  const lastAction = useRef<(() => void) | null>(null);

  useEffect(() => {
    latest.current = state;
  }, [state]);

  const patch = useCallback((p: Partial<FlowState>) => {
    setState((s) => ({ ...s, ...p }));
  }, []);

  const loadInsights = useCallback(
    async (analysis: AnalysisResult, id: number) => {
      patch({ insights: { status: 'loading' } });
      try {
        const result = await api.insights(analysis);
        if (id === runId.current) patch({ insights: { status: 'ready', result } });
      } catch (error) {
        if (id === runId.current) {
          patch({ insights: { status: 'error', error: friendlyError(error) } });
        }
      }
    },
    [api, patch],
  );

  const analyze = useCallback(
    async (request: AnalyzeRequest, fresh: boolean) => {
      const id = ++runId.current;
      setState((s) =>
        fresh || !s.analysis
          ? { ...s, phase: 'analyzing', analysis: null, insights: { status: 'idle' }, error: null }
          : { ...s, reloading: true, error: null },
      );
      try {
        const analysis = await api.analyze(request);
        if (id !== runId.current) return;
        setState((s) => ({ ...s, phase: 'dashboard', request, analysis, reloading: false }));
        void loadInsights(analysis, id);
      } catch (error) {
        if (id !== runId.current) return;
        const friendly = friendlyError(error);
        setState((s) =>
          s.analysis
            ? { ...s, reloading: false, error: friendly }
            : { ...s, phase: 'upload', reloading: false, error: friendly },
        );
      }
    },
    [api, loadInsights],
  );

  const afterParse = useCallback(
    (response: ParseResponse, file: File) => {
      if (response.status === 'needs_mapping') {
        const again = latest.current.phase === 'parsing' && latest.current.parse !== null;
        patch({
          phase: 'mapping',
          file,
          parse: response,
          mappingError: again ? 'Those columns still could not be read. Check the choices.' : null,
        });
        return;
      }
      const request: AnalyzeRequest = {
        holdings: response.holdings,
        base_currency: guessBaseCurrency(response.holdings),
      };
      if (response.unresolved_symbols.length > 0) {
        patch({ phase: 'review', file, parse: response, request, mappingError: null });
        return;
      }
      void analyze(request, true);
    },
    [analyze, patch],
  );

  const parseFile = useCallback(
    async (file: File, mapping?: ColumnMapping) => {
      patch({ phase: 'parsing', error: null, notice: null });
      try {
        afterParse(await api.parse(file, mapping), file);
      } catch (error) {
        const keep = latest.current.parse !== null && mapping !== undefined;
        patch(
          keep
            ? { phase: 'mapping', error: friendlyError(error) }
            : { phase: 'upload', error: friendlyError(error) },
        );
      }
    },
    [api, afterParse, patch],
  );

  const uploadFile = useCallback(
    (file: File) => {
      const problem = validateFile(file);
      if (problem) {
        patch({ error: { title: 'Check your file', message: problem, retryable: false } });
        return;
      }
      const run = () => {
        setState({ ...INITIAL });
        void parseFile(file);
      };
      lastAction.current = run;
      run();
    },
    [parseFile, patch],
  );

  const loadSample = useCallback(
    (name: string) => {
      const run = () => {
        patch({ phase: 'analyzing', analysis: null, error: null, notice: null });
        void (async () => {
          try {
            samples.current ??= await api.samples();
            const info = samples.current.find((s) => s.name === name);
            if (!info) throw new Error('Unknown sample');
            await analyze(
              {
                holdings: info.holdings,
                base_currency: info.base_currency,
                benchmark: info.benchmark,
              },
              true,
            );
          } catch (error) {
            patch({ phase: 'upload', error: friendlyError(error) });
          }
        })();
      };
      lastAction.current = run;
      run();
    },
    [api, analyze, patch],
  );

  const confirmMapping = useCallback(
    (mapping: ColumnMapping) => {
      const file = latest.current.file;
      if (file) void parseFile(file, mapping);
    },
    [parseFile],
  );

  const resolveSymbols = useCallback(
    (fixes: Record<string, string | null>) => {
      const parse = latest.current.parse;
      if (!parse) return;
      let ignored = 0;
      const holdings = parse.holdings.flatMap((h) => {
        const fix = fixes[h.symbol];
        if (fix === undefined) return [h];
        if (fix === null) {
          ignored += 1;
          return [];
        }
        return [{ ...h, symbol: fix }];
      });
      if (holdings.length === 0) {
        patch({
          error: {
            title: 'Nothing left to analyze',
            message: 'Every symbol was ignored.',
            retryable: false,
          },
        });
        return;
      }
      patch({
        notice: ignored > 0 ? `${ignored} symbol${ignored === 1 ? '' : 's'} ignored.` : null,
      });
      void analyze({ holdings, base_currency: guessBaseCurrency(holdings) }, true);
    },
    [analyze, patch],
  );

  const changeControls = useCallback(
    (change: { base_currency?: Currency; benchmark?: string | null }) => {
      const request = latest.current.request;
      if (!request) return;
      const next = { ...request, ...change };
      lastAction.current = () => {
        void analyze(next, false);
      };
      void analyze(next, false);
    },
    [analyze],
  );

  const retryInsights = useCallback(() => {
    const { analysis } = latest.current;
    if (analysis) void loadInsights(analysis, runId.current);
  }, [loadInsights]);

  const reset = useCallback(() => {
    runId.current += 1;
    lastAction.current = null;
    setState(INITIAL);
  }, []);

  const actions: FlowActions = {
    uploadFile,
    loadSample,
    confirmMapping,
    resolveSymbols,
    changeControls,
    retryInsights,
    retry: () => {
      lastAction.current?.();
    },
    dismissError: () => {
      patch({ error: null });
    },
    reset,
  };
  return { state, actions };
}
