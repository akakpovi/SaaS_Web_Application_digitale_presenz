const ACCESS_KEY = "presence_access"
const REFRESH_KEY = "presence_refresh"

export const authStorage = {
  getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_KEY)
  },

  setAccessToken(token: string): void {
    localStorage.setItem(ACCESS_KEY, token)
  },

  clearAccessToken(): void {
    localStorage.removeItem(ACCESS_KEY)
  },

  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_KEY)
  },

  setRefreshToken(token: string): void {
    localStorage.setItem(REFRESH_KEY, token)
  },

  clearRefreshToken(): void {
    localStorage.removeItem(REFRESH_KEY)
  },

  setTokens(access: string, refresh: string): void {
    this.setAccessToken(access)
    this.setRefreshToken(refresh)
  },

  clearAll(): void {
    this.clearAccessToken()
    this.clearRefreshToken()
  },

  hasTokens(): boolean {
    return this.getAccessToken() !== null && this.getRefreshToken() !== null
  },
}
