import { NextRequest, NextResponse } from "next/server";

// Server-side secret: Never exposed to client bundles
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const API_AUTH_TOKEN = process.env.API_AUTH_TOKEN;

async function proxyRequest(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  if (!API_AUTH_TOKEN) {
    return NextResponse.json(
      {
        error: {
          code: "PROXY_NOT_CONFIGURED",
          message: "Backend API authentication is not configured.",
        },
      },
      { status: 503 }
    );
  }

  const { path } = await params;
  const pathStr = path.join("/");
  const searchStr = req.nextUrl.search || "";
  const backendTargetUrl = `${BACKEND_URL}/${pathStr}${searchStr}`;

  const headers = new Headers();
  headers.set("Accept", "application/json");

  const contentType = req.headers.get("content-type");
  if (contentType) {
    headers.set("Content-Type", contentType);
  }

  // Inject server-side secret authorization header
  headers.set("Authorization", `Bearer ${API_AUTH_TOKEN}`);

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
