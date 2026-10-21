import { createBrowserRouter } from 'react-router-dom'

import { AppLayout } from './layouts/AppLayout'
import { AboutPage } from './pages/AboutPage'
import { AISettingsPage } from './pages/AISettingsPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { HomePage } from './pages/HomePage'
import { ImportPage } from './pages/ImportPage'
import { KnowledgeReviewPage } from './pages/KnowledgeReviewPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PracticePage } from './pages/PracticePage'
import { QuestionsPage } from './pages/QuestionsPage'
import { SubjectDetailPage } from './pages/SubjectDetailPage'
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
      { path: 'about', element: <AboutPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
