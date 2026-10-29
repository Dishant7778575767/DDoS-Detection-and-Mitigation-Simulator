import crypto from "crypto";
import { NextRequest, NextResponse } from "next/server";

// Server-side secret: Never exposed to client bundles
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const API_AUTH_TOKEN = process.env.API_AUTH_TOKEN;

function safeTokenCompare(provided: string, expected: string): boolean {
  if (!provided || !expected) {
    return false;
  }
  const bufA = Buffer.from(provided);
  const bufB = Buffer.from(expected);
  if (bufA.length !== bufB.length) {
    return false;
  }
  return crypto.timingSafeEqual(bufA, bufB);
}

function extractCallerToken(req: NextRequest): string {
  const authHeader = req.headers.get("authorization");
  if (authHeader && authHeader.toLowerCase().startsWith("bearer ")) {
    return authHeader.slice(7).trim();
  }
  return "";
}

async function proxyRequest(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathStr = path.join("/");
  const searchStr = req.nextUrl.search || "";
  const backendTargetUrl = `${BACKEND_URL}/${pathStr}${searchStr}`;

  const callerToken = extractCallerToken(req);
  const isPublicHealthProbe = pathStr === "api/v1/health" || pathStr === "health";

  // Security Gate: Protect backend endpoints from unauthorized public proxying.
  // If API_AUTH_TOKEN is configured on this server, caller must provide valid credentials
  // before the proxy injects server credentials or forwards privileged traffic.
  if (API_AUTH_TOKEN && !isPublicHealthProbe) {
    const isValid = safeTokenCompare(callerToken, API_AUTH_TOKEN);
    if (!isValid) {
      return NextResponse.json(
        {
          error: {
            code: "UNAUTHORIZED",
            message: "Authentication required to access SENTRIX proxy. Provide a valid Bearer token.",
          },
        },
        {
          status: 401,
          headers: { "WWW-Authenticate": "Bearer" },
        }
      );
    }
  }

  const headers = new Headers();
  headers.set("Accept", "application/json");

  const contentType = req.headers.get("content-type");
  if (contentType) {
    headers.set("Content-Type", contentType);
  }

  // Forward authorization to backend:
  // If server has API_AUTH_TOKEN and caller was authenticated, inject API_AUTH_TOKEN.
  // Otherwise forward caller's own token if provided.
  if (API_AUTH_TOKEN && callerToken && safeTokenCompare(callerToken, API_AUTH_TOKEN)) {
    headers.set("Authorization", `Bearer ${API_AUTH_TOKEN}`);
  } else if (callerToken) {
    headers.set("Authorization", `Bearer ${callerToken}`);
  }

  let body: BodyInit | null = null;
  if (req.method !== "GET" && req.method !== "HEAD") {
    body = await req.text();
  }

  try {
    const backendRes = await fetch(backendTargetUrl, {
      method: req.method,
      headers,
      body,
      cache: "no-store",
    });

    const resContentType = backendRes.headers.get("content-type") || "application/json";
    const resBody = await backendRes.text();

    return new NextResponse(resBody, {
      status: backendRes.status,
      headers: {
        "Content-Type": resContentType,
      },
    });
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : "Proxy backend unreachable";
    return NextResponse.json(
      {
        error: {
          code: "PROXY_ERROR",
          message: errorMsg,
        },
      },
      { status: 502 }
    );
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
