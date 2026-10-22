import { createBrowserRouter } from 'react-router-dom'

import { AppLayout } from './layouts/AppLayout'
import { AboutPage } from './pages/AboutPage'
import { AdminPage } from './pages/AdminPage'
import { AISettingsPage } from './pages/AISettingsPage'
import { ConnectionSettingsPage } from './pages/ConnectionSettingsPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { HomePage } from './pages/HomePage'
import { ImportPage } from './pages/ImportPage'
import { JoinPage } from './pages/JoinPage'
import { KnowledgeReviewPage } from './pages/KnowledgeReviewPage'
import { LocalDatabasePage } from './pages/LocalDatabasePage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PracticePage } from './pages/PracticePage'
import { QuestionsPage } from './pages/QuestionsPage'
import { SubjectDetailPage } from './pages/SubjectDetailPage'
import { SubjectKnowledgePage } from './pages/SubjectKnowledgePage'
import { SubjectsPage } from './pages/SubjectsPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'import', element: <ImportPage /> },
      { path: 'subjects', element: <SubjectsPage /> },
      { path: 'subjects/:subjectId', element: <SubjectDetailPage /> },
      {
        path: 'subjects/:subjectId/knowledge',
        element: <SubjectKnowledgePage />,
      },
      {
        path: 'subjects/:subjectId/documents',
        element: <DocumentsPage />,
      },
      {
        path: 'documents/:documentId/review',
        element: <KnowledgeReviewPage />,
      },
      { path: 'questions', element: <QuestionsPage /> },
      { path: 'practice', element: <PracticePage /> },
      { path: 'settings/ai', element: <AISettingsPage /> },
      { path: 'settings/connection', element: <ConnectionSettingsPage /> },
      { path: 'settings/local-db', element: <LocalDatabasePage /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'join', element: <JoinPage /> },
      { path: 'admin', element: <AdminPage /> },
      { path: 'about', element: <AboutPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
