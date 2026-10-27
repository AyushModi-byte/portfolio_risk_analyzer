import { useState } from 'react';
import { useApi } from './api/context';
import { ChatDrawer } from './components/ChatDrawer';
import { Dashboard, DashboardSkeleton } from './components/Dashboard';
import { ErrorMessage, Footer, Notice, WakeBanner } from './components/Feedback';
import { MappingDialog } from './components/MappingDialog';
import { UnresolvedPanel } from './components/UnresolvedPanel';
import { UploadScreen } from './components/UploadScreen';
import { useFlow } from './hooks/useFlow';
import { useServerWake } from './hooks/useServerWake';

export function App() {
  const api = useApi();
  const wake = useServerWake(api);
  const { state, actions } = useFlow(api);
  const [chatOpen, setChatOpen] = useState(false);
  const [aiOff, setAiOff] = useState(false);
  const aiAvailable = (wake.health?.ai_available ?? false) && !aiOff;
  const { phase, analysis, request, parse } = state;

  const startOver = () => {
    setChatOpen(false);
    actions.reset();
  };

  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            ◢
          </span>
          <span>Portfolio Risk Analyzer</span>
        </div>
        {phase !== 'upload' && (
          <button type="button" className="btn btn-small" onClick={startOver}>
            New analysis
          </button>
        )}
      </header>

      {(wake.state === 'waking' || wake.state === 'down') && (
        <WakeBanner down={wake.state === 'down'} />
      )}

      <main id="main" className="main">
        {state.error && (
          <ErrorMessage
            error={state.error}
            onRetry={actions.retry}
            onDismiss={actions.dismissError}
          />
        )}
        {state.notice && <Notice>{state.notice}</Notice>}

        {(phase === 'upload' || phase === 'parsing' || phase === 'mapping') && (
          <UploadScreen
            busy={phase === 'parsing'}
            busyLabel="Reading your file…"
            onFile={actions.uploadFile}
            onSample={actions.loadSample}
          />
        )}

        {phase === 'mapping' && parse && (
          <MappingDialog
            parse={parse}
            error={state.mappingError}
            aiAvailable={aiAvailable}
            onSuggest={(headers, rows) => api.suggestMapping(headers, rows)}
            onConfirm={actions.confirmMapping}
            onCancel={actions.reset}
          />
        )}

        {phase === 'review' && parse && (
          <UnresolvedPanel
            symbols={parse.unresolved_symbols}
            onContinue={actions.resolveSymbols}
            onCancel={actions.reset}
          />
        )}

        {phase === 'analyzing' && <DashboardSkeleton />}

        {phase === 'dashboard' && analysis && request && (
          <Dashboard
            analysis={analysis}
            request={request}
            reloading={state.reloading}
            insights={state.insights}
            aiAvailable={aiAvailable}
            onChange={actions.changeControls}
            onRetryInsights={actions.retryInsights}
            onOpenChat={() => {
              setChatOpen(true);
            }}
          />
        )}
      </main>

      {chatOpen && analysis && (
        <ChatDrawer
          analysis={analysis}
          request={request}
          aiAvailable={aiAvailable}
          onClose={() => {
            setChatOpen(false);
          }}
          onAiUnavailable={() => {
            setAiOff(true);
          }}
        />
      )}

      <Footer />
    </div>
  );
}
