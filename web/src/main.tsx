import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { readConfig } from './app/config';
import { BroadcastView } from './views/BroadcastView';
import { WebApp } from './views/WebApp';
import './styles/app.css';

const config = readConfig();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {config.view === 'broadcast' ? <BroadcastView config={config} /> : <WebApp config={config} />}
  </StrictMode>,
);
