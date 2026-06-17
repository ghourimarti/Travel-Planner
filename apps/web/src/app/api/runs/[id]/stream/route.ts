import { streamRun } from "@/lib/api";

export const dynamic = "force-dynamic";

/**
 * SSE pass-through. The browser's EventSource can't send an Authorization header,
 * so it hits this same-origin route, which attaches the Auth0 token server-side
 * and pipes the backend's text/event-stream straight back to the client.
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await params;
  try {
    const upstream = await streamRun(id, request.signal);
    if (!upstream.ok || !upstream.body) {
      return new Response(`data: ${JSON.stringify({ type: "error", detail: "stream unavailable" })}\n\n`, {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      });
    }
    return new Response(upstream.body, {
      headers: {
        "content-type": "text/event-stream",
        "cache-control": "no-cache, no-transform",
        connection: "keep-alive",
      },
    });
  } catch {
    return new Response(`data: ${JSON.stringify({ type: "error", detail: "stream failed" })}\n\n`, {
      status: 200,
      headers: { "content-type": "text/event-stream" },
    });
  }
}
