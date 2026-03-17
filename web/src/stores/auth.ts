import { create } from "zustand";
import { api, clearTokens, getAccessToken } from "@/lib/api";

export interface AuthUser {
  id: string;
  username: string;
  is_active: boolean;
  is_public: boolean;
  avatar_url: string | null;
}

interface AuthState {
  user: AuthUser | null;
  isLoading: boolean;
  isInitialized: boolean;
  fetchUser: () => Promise<void>;
  logout: () => void;
  setUser: (user: AuthUser) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,
  isInitialized: false,

  fetchUser: async () => {
    if (!getAccessToken()) {
      set({ isInitialized: true, user: null });
      return;
    }
    set({ isLoading: true });
    try {
      const user = await api.get<AuthUser>("/users/me");
      set({ user, isLoading: false, isInitialized: true });
    } catch {
      clearTokens();
      set({ user: null, isLoading: false, isInitialized: true });
    }
  },

  logout: () => {
    clearTokens();
    set({ user: null });
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  },

  setUser: (user: AuthUser) => set({ user }),
}));
