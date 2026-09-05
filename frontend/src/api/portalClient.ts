import { ApiError } from "@/api/client";

// Deliberately separate from api/client.ts: a portal token is never the internal JWT in
// localStorage, so this never reads or writes that storage -- it only ever sends the one
// token it's given, scoped to one quotation.
async function portalRequest<T>(portalToken: string, path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${portalToken}`,
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(`/api${path}`, { ...options, headers });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // no JSON body
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export const portalApi = {
  get: <T>(portalToken: string, path: string) => portalRequest<T>(portalToken, path, { method: "GET" }),
  post: <T>(portalToken: string, path: string, body?: unknown) =>
    portalRequest<T>(portalToken, path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
};
