import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { LanguageProvider } from './i18n';
import { WorkspaceProvider } from './workspace';
import './style.css';
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><LanguageProvider><WorkspaceProvider><App/></WorkspaceProvider></LanguageProvider></React.StrictMode>);
