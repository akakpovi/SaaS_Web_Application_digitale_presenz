import React, { Suspense } from 'react'
import ReactDOM from 'react-dom/client'
import { HelmetProvider } from 'react-helmet-async'
import { LangProvider } from './context/LangContext'
import { AuthProvider } from './context/AuthContext'
import App from './App'
import './i18n'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HelmetProvider>
      <LangProvider>
        <AuthProvider>
          <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"/></div>}>
            <App />
          </Suspense>
        </AuthProvider>
      </LangProvider>
    </HelmetProvider>
  </React.StrictMode>,
)
