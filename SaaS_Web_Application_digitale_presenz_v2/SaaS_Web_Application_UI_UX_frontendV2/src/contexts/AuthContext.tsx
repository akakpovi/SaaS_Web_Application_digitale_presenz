import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react"
import { api } from "../api/client"
import { endpoints } from "../api/endpoints"
import { authStorage } from "../api/authStorage"
import type {
  User,
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  RegisterResponse,
  PasswordResetRequest,
  PasswordResetConfirmRequest,
} from "../api/types"

interface AuthContextValue {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean

  login: (credentials: LoginRequest) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
  requestPasswordReset: (data: PasswordResetRequest) => Promise<void>
  resetPassword: (data: PasswordResetConfirmRequest) => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    try {
      const userData = await api.get<User>(endpoints.auth.me)
      setUser(userData)
    } catch {
      setUser(null)
    }
  }, [])

  useEffect(() => {
    const initializeAuth = async () => {
      const accessToken = authStorage.getAccessToken()
      const refreshToken = authStorage.getRefreshToken()

      if (!accessToken || !refreshToken) {
        setIsLoading(false)
        return
      }

      try {
        await refreshUser()
      } catch {
        authStorage.clearAll()
        setUser(null)
      } finally {
        setIsLoading(false)
      }
    }

    initializeAuth()
  }, [refreshUser])

  const login = async (credentials: LoginRequest): Promise<void> => {
    const response = await api.post<AuthResponse>(
      endpoints.auth.login,
      credentials,
    )
    authStorage.setTokens(response.access, response.refresh)
    setUser(response.user)
  }

  const register = async (data: RegisterRequest): Promise<void> => {
    await api.post<RegisterResponse>(endpoints.auth.register, data)
  }

  const logout = async (): Promise<void> => {
    try {
      const refreshToken = authStorage.getRefreshToken()
      if (refreshToken) {
        await api.post(endpoints.auth.logout, { refresh: refreshToken })
      }
    } finally {
      authStorage.clearAll()
      setUser(null)
    }
  }

  const requestPasswordReset = async (
    data: PasswordResetRequest,
  ): Promise<void> => {
    await api.post(endpoints.auth.passwordReset, data)
  }

  const resetPassword = async (
    data: PasswordResetConfirmRequest,
  ): Promise<void> => {
    await api.post(endpoints.auth.passwordResetConfirm, data)
  }

  const value: AuthContextValue = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    register,
    logout,
    refreshUser,
    requestPasswordReset,
    resetPassword,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
