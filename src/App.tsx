import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { RoleRoute } from './components/layout/RoleRoute';

import Login from './pages/auth/Login';
import Unauthorized from './pages/auth/Unauthorized';
import ForgotPassword from './pages/auth/ForgotPassword';
import ResetPassword from './pages/auth/ResetPassword';
import ChangePassword from './pages/auth/ChangePassword';
import AdminDashboard from './pages/admin/Dashboard';
import Sessions from './pages/admin/Sessions';
import Batches from './pages/admin/Batches';
import BatchDetail from './pages/admin/BatchDetail';
import Faculty from './pages/admin/Faculty';
import FacultyRegister from './pages/auth/FacultyRegister';
import FacultyRequestDetails from './pages/admin/FacultyRequestDetails';
import AdminAttendance from './pages/admin/Attendance';
import AdminAnalytics from './pages/admin/Analytics';
import AdminSettings from './pages/admin/Settings';

import FacultyDashboard from './pages/faculty/Dashboard';
import LiveAttendance from './pages/faculty/LiveAttendance';
import FacultyHistory from './pages/faculty/History';
import MyBatches from './pages/faculty/MyBatches';

import StudentHome from './pages/student/Home';
import Profile from './pages/student/Profile';
import Enrollment from './pages/student/Enrollment';
import StudentAttendance from './pages/student/Attendance';

function RootRedirect() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={`/${user.role}`} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/login" element={<Login />} />
          <Route path="/faculty/register" element={<FacultyRegister />} />
          <Route path="/unauthorized" element={<Unauthorized />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route
            path="/reset-password"
            element={<ResetPassword />}
          />

          <Route
            path="/reset-password/:token"
            element={<ResetPassword />}
          />
          <Route
            path="/change-password"
            element={<ChangePassword />}
          />
          <Route path="/admin" element={<RoleRoute allow={['admin']}><AdminDashboard /></RoleRoute>} />
          <Route path="/admin/sessions" element={<RoleRoute allow={['admin']}><Sessions /></RoleRoute>} />
          <Route path="/admin/batches" element={<RoleRoute allow={['admin']}><Batches /></RoleRoute>} />
          <Route path="/admin/batches/:id" element={<RoleRoute allow={['admin']}><BatchDetail /></RoleRoute>} />
          <Route path="/admin/faculty" element={<RoleRoute allow={['admin']}><Faculty /></RoleRoute>} />
          <Route
            path="/admin/faculty/requests/:id"
            element={
              <RoleRoute allow={['admin']}>
                <FacultyRequestDetails />
              </RoleRoute>
            }
          />
          <Route path="/admin/attendance" element={<RoleRoute allow={['admin']}><AdminAttendance /></RoleRoute>} />
          <Route path="/admin/analytics" element={<RoleRoute allow={['admin']}><AdminAnalytics /></RoleRoute>} />
          <Route path="/admin/settings" element={<RoleRoute allow={['admin']}><AdminSettings /></RoleRoute>} />

          <Route path="/faculty" element={<RoleRoute allow={['faculty']}><FacultyDashboard /></RoleRoute>} />
          <Route path="/faculty/live" element={<RoleRoute allow={['faculty']}><LiveAttendance /></RoleRoute>} />
          <Route path="/faculty/history" element={<RoleRoute allow={['faculty']}><FacultyHistory /></RoleRoute>} />
          <Route path="/faculty/batches" element={<RoleRoute allow={['faculty']}><MyBatches /></RoleRoute>} />

          <Route path="/student" element={<RoleRoute allow={['student']}><StudentHome /></RoleRoute>} />
          <Route path="/student/profile" element={<RoleRoute allow={['student']}><Profile /></RoleRoute>} />
          <Route path="/student/enrollment" element={<RoleRoute allow={['student']}><Enrollment /></RoleRoute>} />
          <Route path="/student/attendance" element={<RoleRoute allow={['student']}><StudentAttendance /></RoleRoute>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
