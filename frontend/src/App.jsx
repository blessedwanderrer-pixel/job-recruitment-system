import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import { LoginPage, SetPasswordPage, SignupPage } from './pages/AuthPages'
import { ApplicationsPage, CvPage, JobDetailPage, JobsPage } from './pages/CandidatePages'
import { RecruiterApplicationPage, RecruiterJobPage, RecruiterJobsPage } from './pages/RecruiterPages'
import {
  AdminDashboardPage,
  AdminJobDetailPage,
  AdminJobNewPage,
  AdminJobsPage,
  AdminRecruitersPage,
} from './pages/AdminPages'
import { RequireAuth, Shell } from './ui'

function HomeRedirect() {
  const { loading, profile } = useAuth()
  if (loading) return <p className="muted">Loading…</p>
  if (!profile) return <Navigate to="/login" replace />
  if (profile.role === 'admin') return <Navigate to="/admin/dashboard" replace />
  if (profile.role === 'recruiter') return <Navigate to="/recruiter/jobs" replace />
  return <Navigate to="/jobs" replace />
}

function AppRoutes() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<HomeRedirect />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/set-password" element={<SetPasswordPage />} />
        <Route
          path="/jobs"
          element={
            <RequireAuth role="candidate">
              <JobsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/jobs/:id"
          element={
            <RequireAuth role="candidate">
              <JobDetailPage />
            </RequireAuth>
          }
        />
        <Route
          path="/cv"
          element={
            <RequireAuth role="candidate">
              <CvPage />
            </RequireAuth>
          }
        />
        <Route
          path="/applications"
          element={
            <RequireAuth role="candidate">
              <ApplicationsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/recruiter/jobs"
          element={
            <RequireAuth role="recruiter">
              <RecruiterJobsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/recruiter/jobs/:id"
          element={
            <RequireAuth role="recruiter">
              <RecruiterJobPage />
            </RequireAuth>
          }
        />
        <Route
          path="/recruiter/applications/:id"
          element={
            <RequireAuth role="recruiter">
              <RecruiterApplicationPage />
            </RequireAuth>
          }
        />
        <Route
          path="/admin/dashboard"
          element={
            <RequireAuth role="admin">
              <AdminDashboardPage />
            </RequireAuth>
          }
        />
        <Route
          path="/admin/recruiters"
          element={
            <RequireAuth role="admin">
              <AdminRecruitersPage />
            </RequireAuth>
          }
        />
        <Route
          path="/admin/jobs"
          element={
            <RequireAuth role="admin">
              <AdminJobsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/admin/jobs/new"
          element={
            <RequireAuth role="admin">
              <AdminJobNewPage />
            </RequireAuth>
          }
        />
        <Route
          path="/admin/jobs/:id"
          element={
            <RequireAuth role="admin">
              <AdminJobDetailPage />
            </RequireAuth>
          }
        />
      </Routes>
    </Shell>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}
