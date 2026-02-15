import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import Campaigns from "./pages/Campaigns";
import Doorways from "./pages/Doorways";
import Templates from "./pages/Templates";
import Keywords from "./pages/Keywords";
import Servers from "./pages/Servers";
import Domains from "./pages/Domains";
import Analytics from "./pages/Analytics";
import SettingsPage from "./pages/Settings";
import Offers from "./pages/Offers";
import UsersPage from "./pages/Users";
import Seo from "./pages/Seo";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token, isLoading } = useAuth();
  if (isLoading) return <div className="flex items-center justify-center min-h-screen text-slate-400">Загрузка...</div>;
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Navigate to="/login" replace />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="campaigns" element={<Campaigns />} />
          <Route path="doorways" element={<Doorways />} />
          <Route path="templates" element={<Templates />} />
          <Route path="keywords" element={<Keywords />} />
          <Route path="servers" element={<Servers />} />
          <Route path="domains" element={<Domains />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="offers" element={<Offers />} />
          <Route path="seo" element={<Seo />} />
          <Route path="users" element={<UsersPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
