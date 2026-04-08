"use client";

export interface JWTClaims {
  sub: string;
  dept: string;
  role: string;
  permissions: string[];
  proposal_id?: string;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("auth_token");
}

export function setToken(token: string): void {
  sessionStorage.setItem("auth_token", token);
}

export function clearToken(): void {
  sessionStorage.removeItem("auth_token");
}

export function decodeTokenPayload(token: string): JWTClaims | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return {
      sub: payload.sub,
      dept: payload.dept,
      role: payload.role,
      permissions: payload.permissions || [],
      proposal_id: payload.proposal_id,
    };
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return true;
    const payload = JSON.parse(atob(parts[1]));
    return payload.exp * 1000 < Date.now();
  } catch {
    return true;
  }
}
