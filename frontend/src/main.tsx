import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { LanguageProvider } from './i18n';
import { AuthProvider } from './auth';
import { WorkspaceProvider } from './workspace';
import './app/styles/style.css';
import './app/styles/auth.css';
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><LanguageProvider><AuthProvider><WorkspaceProvider><App/></WorkspaceProvider></AuthProvider></LanguageProvider></React.StrictMode>);
