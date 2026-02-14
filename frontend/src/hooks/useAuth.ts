import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  setTokens: (access: string, refresh: string) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      refreshToken: null,
      isLoading: false,
      setTokens: (access, refresh) => set({ token: access, refreshToken: refresh }),
      logout: () => set({ token: null, refreshToken: null }),
    }),
    { name: "dorvey-auth" }
  )
);
