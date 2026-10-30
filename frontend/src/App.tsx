import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { Loading } from "./components/ui";
import { Landing } from "./pages/Landing";
import { Login, Register } from "./pages/AuthPages";
import { Dashboard } from "./pages/Dashboard";
import { Tutor, AskDocuments } from "./pages/Tutor";
import { Documents } from "./pages/Documents";
import { Lessons } from "./pages/Lessons";
import { Quizzes } from "./pages/Quizzes";
import { ProgressPage } from "./pages/Progress";
import { MemoryPage } from "./pages/Memory";
import { Billing } from "./pages/Billing";
import { UsagePage } from "./pages/Usage";
import { Profile } from "./pages/Profile";
import { Admin } from "./pages/Admin";

function Protected({ admin }: { admin?: boolean }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <div className="boot"><Loading label="Restoring your session" /></div>;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  if (admin && user.role !== "admin") return <Navigate to="/app" replace />;
  return <Layout />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<Protected />}>
        <Route path="/app" element={<Dashboard />} />
        <Route path="/tutor" element={<Tutor />} />
        <Route path="/ask" element={<AskDocuments />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/lessons" element={<Lessons />} />
        <Route path="/quizzes" element={<Quizzes />} />
        <Route path="/progress" element={<ProgressPage />} />
        <Route path="/memory" element={<MemoryPage />} />
        <Route path="/usage" element={<UsagePage />} />
        <Route path="/billing" element={<Billing />} />
        <Route path="/profile" element={<Profile />} />
      </Route>
      <Route element={<Protected admin />}><Route path="/admin" element={<Admin />} /></Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
