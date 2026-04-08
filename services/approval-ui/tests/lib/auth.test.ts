import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  decodeTokenPayload,
  isTokenExpired,
  getToken,
  setToken,
  clearToken,
} from "@/lib/auth";

/**
 * Helper: build a fake JWT with a given payload object.
 * The header and signature are dummy values — only the payload matters.
 */
function fakeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.fake-signature`;
}

describe("decodeTokenPayload", () => {
  it("decodes a valid JWT payload and returns correct claims", () => {
    const token = fakeJwt({
      sub: "user-123",
      dept: "treasury",
      role: "hod",
      permissions: ["approve", "reject"],
      proposal_id: "chg_0001",
    });

    const claims = decodeTokenPayload(token);

    expect(claims).not.toBeNull();
    expect(claims!.sub).toBe("user-123");
    expect(claims!.dept).toBe("treasury");
    expect(claims!.role).toBe("hod");
    expect(claims!.permissions).toEqual(["approve", "reject"]);
    expect(claims!.proposal_id).toBe("chg_0001");
  });

  it("returns null for a malformed string (not 3 parts)", () => {
    expect(decodeTokenPayload("not-a-jwt")).toBeNull();
    expect(decodeTokenPayload("two.parts")).toBeNull();
  });

  it("returns null for invalid base64 payload", () => {
    expect(decodeTokenPayload("a.!!!invalid!!!.c")).toBeNull();
  });

  it("defaults permissions to empty array when not present", () => {
    const token = fakeJwt({ sub: "u", dept: "d", role: "r" });
    const claims = decodeTokenPayload(token);

    expect(claims).not.toBeNull();
    expect(claims!.permissions).toEqual([]);
  });
});

describe("isTokenExpired", () => {
  it("returns false when exp is in the future", () => {
    const futureExp = Math.floor(Date.now() / 1000) + 3600; // 1 hour ahead
    const token = fakeJwt({ exp: futureExp });

    expect(isTokenExpired(token)).toBe(false);
  });

  it("returns true when exp is in the past", () => {
    const pastExp = Math.floor(Date.now() / 1000) - 3600; // 1 hour ago
    const token = fakeJwt({ exp: pastExp });

    expect(isTokenExpired(token)).toBe(true);
  });

  it("returns true for malformed token", () => {
    expect(isTokenExpired("garbage")).toBe(true);
  });
});

describe("getToken / setToken / clearToken round-trip", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("returns null when no token is stored", () => {
    expect(getToken()).toBeNull();
  });

  it("stores and retrieves a token", () => {
    setToken("my-token-value");
    expect(getToken()).toBe("my-token-value");
  });

  it("clears the stored token", () => {
    setToken("to-be-cleared");
    clearToken();
    expect(getToken()).toBeNull();
  });
});
