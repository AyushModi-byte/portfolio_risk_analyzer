import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { apiBaseUrl, createApi } from './api/client';
import { ApiContext } from './api/context';
import { ConfigError } from './components/ConfigError';
import './index.css';

const root = document.getElementById('root');
if (!root) throw new Error('Missing #root element');

const baseUrl = apiBaseUrl();

createRoot(root).render(
  <StrictMode>
    {baseUrl ? (
      <ApiContext.Provider value={createApi(baseUrl)}>
        <App />
      </ApiContext.Provider>
    ) : (
      <ConfigError />
    )}
  </StrictMode>,
);
