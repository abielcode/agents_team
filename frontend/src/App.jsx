import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import ProjectSetup from './pages/ProjectSetup'
import PRDBuilder from './pages/PRDBuilder'
import ProductBacklog from './pages/ProductBacklog'
import SprintBoard from './pages/SprintBoard'
import AgentConsole from './pages/AgentConsole'
import TeamConfig from './pages/TeamConfig'
import SprintReview from './pages/SprintReview'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/projects" replace />} />
        <Route path="projects" element={<ProjectSetup />} />
        <Route path="projects/:projectId/prd" element={<PRDBuilder />} />
        <Route path="projects/:projectId/backlog" element={<ProductBacklog />} />
        <Route path="projects/:projectId/sprints/:sprintId" element={<SprintBoard />} />
        <Route path="projects/:projectId/sprints/:sprintId/console" element={<AgentConsole />} />
        <Route path="projects/:projectId/config" element={<TeamConfig />} />
        <Route path="projects/:projectId/sprints/:sprintId/review" element={<SprintReview />} />
      </Route>
    </Routes>
  )
}
