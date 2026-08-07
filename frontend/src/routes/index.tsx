import {createBrowserRouter} from 'react-router-dom'
import {BasicLayout} from '@/layouts/BasicLayout'
import {HomePage} from '@/pages/HomePage'
import {DocumentsPage} from '@/pages/DocumentsPage'
import {DocumentDetailPage} from '@/pages/DocumentDetailPage'
import {ChatPage} from '@/pages/ChatPage'
import {EvaluationListPage} from '@/pages/EvaluationListPage'
import {EvaluationDetailPage} from '@/pages/EvaluationDetailPage'

export const router = createBrowserRouter([
    {
        path: '/',
        element: <BasicLayout/>,
        children: [
            {index: true, element: <HomePage/>},
            {path: 'documents', element: <DocumentsPage/>},
            {path: 'documents/:id', element: <DocumentDetailPage/>},
            {path: 'chat', element: <ChatPage/>},
            {path: 'evaluation', element: <EvaluationListPage/>},
            {path: 'evaluation/runs/:id', element: <EvaluationDetailPage/>},
        ],
    },
])