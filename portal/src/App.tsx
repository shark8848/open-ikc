import { useState } from 'react'
import { hasAdminToken } from './api/client'
import { Layout } from './components/Layout'
import type { PageKey } from './components/Layout'
import { FeedbackProvider } from './components/feedback'
import { Dashboard } from './pages/Dashboard'
import { Endpoints } from './pages/Endpoints'
import { Login } from './pages/Login'
import { TestLab } from './pages/TestLab'
import { Tokens } from './pages/Tokens'

export default function App() {
  const [authed, setAuthed] = useState(hasAdminToken())
  const [page, setPage] = useState<PageKey>('dashboard')

  return (
    <FeedbackProvider>
      {!authed ? (
        <Login onLoggedIn={() => setAuthed(true)} />
      ) : (
        <Layout page={page} onNavigate={setPage} onLogout={() => setAuthed(false)}>
          {page === 'dashboard' ? <Dashboard /> : null}
          {page === 'endpoints' ? <Endpoints /> : null}
          {page === 'tokens' ? <Tokens /> : null}
          {page === 'testlab' ? <TestLab /> : null}
        </Layout>
      )}
    </FeedbackProvider>
  )
}
