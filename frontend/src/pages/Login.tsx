import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/client";
import { useAuth } from "../hooks/useAuth";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [needs2fa, setNeeds2fa] = useState(false);
  const [tempToken, setTempToken] = useState("");
  const [code2fa, setCode2fa] = useState("");
  const { setTokens } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", { email, password });
      if (data.requires_2fa && data.temp_token) {
        setNeeds2fa(true);
        setTempToken(data.temp_token);
      } else {
        setTokens(data.access_token, data.refresh_token);
        navigate("/");
      }
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail ?? "Ошибка входа");
    } finally {
      setLoading(false);
    }
  };

  const handleBootstrapAdmin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/auth/bootstrap-admin", { email, password });
      setError("");
      const { data } = await api.post("/auth/login", { email, password });
      setTokens(data.access_token, data.refresh_token);
      navigate("/");
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail ?? "Ошибка");
    } finally {
      setLoading(false);
    }
  };

  const handle2fa = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login/2fa", { code: code2fa, temp_token: tempToken });
      setTokens(data.access_token, data.refresh_token);
      navigate("/");
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } };
      setError(ax?.response?.data?.detail ?? "Неверный код");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-emerald-400">Dorvey</h1>
          <p className="text-slate-400 mt-1">Система умных дорвеев</p>
        </div>
        <form onSubmit={needs2fa ? handle2fa : handleSubmit} className="bg-slate-800/80 rounded-xl p-6 shadow-xl border border-slate-700">
          <h2 className="text-lg font-semibold text-white mb-4">{needs2fa ? "Код 2FA" : "Вход"}</h2>
          {error && <p className="text-red-400 text-sm mb-4">{error}</p>}
          {needs2fa ? (
            <div className="space-y-4">
              <input
                type="text"
                value={code2fa}
                onChange={(e) => setCode2fa(e.target.value)}
                placeholder="6-значный код"
                maxLength={6}
                className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
              <button type="submit" disabled={loading || code2fa.length < 6}
                className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg disabled:opacity-50">
                {loading ? "Проверка..." : "Подтвердить"}
              </button>
              <button type="button" onClick={() => { setNeeds2fa(false); setTempToken(""); setCode2fa(""); }}
                className="w-full text-slate-400 hover:text-white text-sm">Назад</button>
            </div>
          ) : (
          <div className="space-y-4">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              required
              className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Пароль"
              required
              className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              {loading ? "Вход..." : "Войти"}
            </button>
            <button
              type="button"
              onClick={handleBootstrapAdmin}
              disabled={loading || !email || !password}
              className="w-full py-2 text-slate-400 hover:text-amber-400 text-sm"
            >
              Назначить себя администратором (если первый пользователь)
            </button>
          </div>
          )}
        </form>
      </div>
    </div>
  );
}
