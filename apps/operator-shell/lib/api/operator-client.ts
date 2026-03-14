import type {
  BootstrapPayload,
  ChatStreamEvent,
  ChatTurnInput,
  ChatTurnResult,
  CompanyDetailPayload,
  CompanyListPayload,
  CreateSegmentInput,
  CreateSegmentResult,
  FeedbackSubmissionInput,
  FeedbackSubmissionResult,
  LoginResult,
  SegmentDetailPayload,
  SegmentExportResult,
  SegmentListPayload,
  ThreadDetailPayload,
  ThreadListPayload,
} from "@/lib/types/operator";

const API_ROOT = "/operator-api";
const CHAT_RUNTIME_ROOT = "/chat-api";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  if (!headers.has("Content-Type")) {
    if (init?.body instanceof URLSearchParams) {
      headers.set("Content-Type", "application/x-www-form-urlencoded;charset=UTF-8");
    } else if (!(init?.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
  }

  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response
      .json()
      .catch(() => ({ detail: `${response.status} ${response.statusText}` }));
    const message =
      typeof detail.detail === "string"
        ? detail.detail
        : detail.detail?.error || `${response.status} ${response.statusText}`;
    throw new Error(message);
  }

  return (await response.json()) as T;
}

async function* requestStreamJson<T>(
  path: string,
  init?: RequestInit,
): AsyncGenerator<T, void, undefined> {
  const response = await fetch(`${CHAT_RUNTIME_ROOT}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    credentials: "same-origin",
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response
      .json()
      .catch(() => ({ detail: `${response.status} ${response.statusText}` }));
    const message =
      typeof detail.detail === "string"
        ? detail.detail
        : detail.detail?.error || `${response.status} ${response.statusText}`;
    throw new Error(message);
  }

  if (!response.body) {
    throw new Error("Streaming response body is unavailable.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    let newlineIndex = buffer.indexOf("\n");
    while (newlineIndex >= 0) {
      const line = buffer.slice(0, newlineIndex).trim();
      buffer = buffer.slice(newlineIndex + 1);
      if (line) {
        yield JSON.parse(line) as T;
      }
      newlineIndex = buffer.indexOf("\n");
    }

    if (done) {
      break;
    }
  }

  const trailing = buffer.trim();
  if (trailing) {
    yield JSON.parse(trailing) as T;
  }
}

export const operatorClient = {
  getBootstrap() {
    return requestJson<BootstrapPayload>("/bootstrap");
  },
  login(username: string, password: string) {
    const body = new URLSearchParams();
    body.set("username", username);
    body.set("password", password);
    return requestJson<LoginResult>("/auth/login", {
      method: "POST",
      body,
    });
  },
  logout() {
    return requestJson<{ status: string }>("/auth/logout", {
      method: "POST",
    });
  },
  getThreads(search: string) {
    const query = new URLSearchParams();
    if (search.trim()) {
      query.set("search", search.trim());
    }
    return requestJson<ThreadListPayload>(`/threads?${query.toString()}`);
  },
  getThread(threadId: string) {
    return requestJson<ThreadDetailPayload>(`/threads/${threadId}`);
  },
  getCompanies(params: { query: string; city: string; status: string }) {
    const search = new URLSearchParams();
    if (params.query.trim()) {
      search.set("q", params.query.trim());
    }
    if (params.city.trim()) {
      search.set("city", params.city.trim());
    }
    if (params.status.trim()) {
      search.set("status", params.status.trim());
    }
    return requestJson<CompanyListPayload>(`/companies?${search.toString()}`);
  },
  getCompany(companyRef: string) {
    return requestJson<CompanyDetailPayload>(`/companies/${companyRef}`);
  },
  getSegments(searchTerm: string) {
    const query = new URLSearchParams();
    if (searchTerm.trim()) {
      query.set("search", searchTerm.trim());
    }
    return requestJson<SegmentListPayload>(`/segments?${query.toString()}`);
  },
  getSegment(segmentRef: string) {
    return requestJson<SegmentDetailPayload>(`/segments/${segmentRef}`);
  },
  createSegment(payload: CreateSegmentInput) {
    return requestJson<CreateSegmentResult>("/segments", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  exportSegment(segmentRef: string) {
    return requestJson<SegmentExportResult>(`/segments/${segmentRef}/export`, {
      method: "POST",
    });
  },
  submitFeedback(payload: FeedbackSubmissionInput) {
    const body = new FormData();
    body.set("surface", payload.surface);
    body.set("feedback_text", payload.feedbackText);
    if (payload.pagePath) {
      body.set("page_path", payload.pagePath);
    }
    if (payload.pageUrl) {
      body.set("page_url", payload.pageUrl);
    }
    if (payload.threadId) {
      body.set("thread_id", payload.threadId);
    }
    if (payload.companyRef) {
      body.set("company_ref", payload.companyRef);
    }
    if (payload.segmentRef) {
      body.set("segment_ref", payload.segmentRef);
    }
    body.set("context_json", JSON.stringify(payload.context ?? {}));
    for (const screenshot of payload.screenshots ?? []) {
      body.append("screenshots", screenshot);
    }
    return requestJson<FeedbackSubmissionResult>("/feedback", {
      method: "POST",
      body,
    });
  },
  streamChatTurn(payload: ChatTurnInput) {
    return requestStreamJson<ChatStreamEvent>("/chat/stream", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  async sendChatTurn(payload: ChatTurnInput) {
    let threadId = payload.thread_id ?? null;
    let toolCalls: string[] = [];
    let suggestedActions: ChatTurnResult["suggested_actions"] = [];
    let message: ChatTurnResult["message"] | null = null;

    for await (const event of operatorClient.streamChatTurn(payload)) {
      if (event.type === "thread") {
        threadId = event.thread_id;
      } else if (event.type === "assistant_message") {
        threadId = event.thread_id;
        toolCalls = event.tool_calls;
        suggestedActions = event.suggested_actions ?? [];
        message = event.message;
      } else if (event.type === "error") {
        throw new Error(event.error);
      }
    }

    if (!message) {
      throw new Error("No assistant message was returned by the chat runtime.");
    }

    return {
      thread_id: threadId,
      tool_calls: toolCalls,
      suggested_actions: suggestedActions,
      message,
    } satisfies ChatTurnResult;
  },
};
