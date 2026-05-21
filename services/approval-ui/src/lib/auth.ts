import { env } from "./env";

// Roles allowed to access the approval dashboard
const ALLOWED_ROLES = ["ceo", "admin", "department_head", "hr_manager"];

export interface JWTClaims {
  sub: string;
  email?: string;
  dept?: string;
  role: string;
  permissions: string[];
  proposal_id?: string;
  departmentId?: string;
  departmentSlug?: string;
}

export interface SessionUser {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  role: string;
  permissions: string[];
  dept: string;
}

// ─── Token storage ───────────────────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("auth_token");
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem("auth_token", token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem("auth_token");
}

// ─── Session user storage ────────────────────────────────────────────────────

export function getSessionUser(): SessionUser | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem("session_user");
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export function setSessionUser(user: SessionUser): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem("session_user", JSON.stringify(user));
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem("auth_token");
  sessionStorage.removeItem("session_user");
}

// ─── JWT decode helpers ──────────────────────────────────────────────────────

export function decodeTokenPayload(token: string): JWTClaims | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return {
      sub: payload.sub,
      email: payload.email,
      dept: payload.dept ?? payload.departmentSlug,
      role: payload.role,
      permissions: payload.permissions || derivePermissions(payload.role),
      proposal_id: payload.proposal_id,
      departmentId: payload.departmentId,
      departmentSlug: payload.departmentSlug,
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

// ─── Permission helpers ──────────────────────────────────────────────────────

export function derivePermissions(role: string): string[] {
  const perms = ["read"];
  if (role === "ceo" || role === "admin") {
    perms.push("approve", "reject", "edit", "escalate");
  } else if (role === "department_head" || role === "hr_manager") {
    perms.push("approve", "reject");
  }
  return perms;
}

export function isAllowedRole(role: string): boolean {
  return ALLOWED_ROLES.includes(role);
}

// ─── Login via main portal backend ───────────────────────────────────────────

export async function loginWithCredentials(
  email: string,
  password: string,
): Promise<SessionUser> {
  const res = await fetch(`${env.NEXT_PUBLIC_PORTAL_API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "Invalid email or password");
  }

  const data = await res.json();

  if (!isAllowedRole(data.user.role)) {
    throw new Error("You do not have permission to access the approval dashboard");
  }

  // Store the access token (same JWT secret, works with gateway)
  setToken(data.accessToken);

  // Pull the dept from the JWT — portal-issued tokens carry `departmentSlug`.
  // Fall back to "cac" only if neither the token nor the user payload carries one.
  const decoded = decodeTokenPayload(data.accessToken);
  const dept =
    decoded?.dept ??
    decoded?.departmentSlug ??
    data.user.departmentSlug ??
    data.user.dept ??
    "cac";

  const user: SessionUser = {
    id: data.user.id,
    email: data.user.email,
    firstName: data.user.firstName,
    lastName: data.user.lastName,
    role: data.user.role,
    permissions: derivePermissions(data.user.role),
    dept,
  };

  setSessionUser(user);
  return user;
}

// ─── Check if user has an active session ─────────────────────────────────────

export function hasActiveSession(): boolean {
  const token = getToken();
  if (!token) return false;
  return !isTokenExpired(token);
}
