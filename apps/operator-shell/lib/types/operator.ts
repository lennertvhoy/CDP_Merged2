export type TabId =
  | "chat"
  | "threads"
  | "companies"
  | "segments"
  | "sources"
  | "pipelines"
  | "activity"
  | "settings";

export type SurfaceMode = "backend" | "mock";

export interface SurfaceDescriptor {
  mode: SurfaceMode;
  status: string;
  detail: string;
}

export interface BootstrapPayload {
  status: string;
  phase: "access_gate" | "app";
  health: {
    service: string;
    query_plane: string;
    companies_table: string;
  } | null;
  session: {
    mode: string;
    authenticated: boolean;
    user: {
      identifier?: string | null;
      display_name?: string | null;
      is_admin?: boolean;
    } | null;
    auth: {
      required: boolean;
      password_enabled: boolean;
      password_mode: "local-accounts" | "shared-secret" | null;
    };
    detail: string;
    gate: {
      title: string;
      subtitle: string;
      help: string;
    } | null;
  };
  surfaces: Record<TabId, SurfaceDescriptor> | null;
}

export interface LoginResult {
  status: string;
  user: {
    identifier: string;
    display_name: string | null;
  };
}

export interface ThreadSummary {
  id: string;
  title: string;
  updated_at: string;
  created_at: string;
  user_identifier: string | null;
  total_steps: number;
  user_messages: number;
  preview: string | null;
  resume_context: {
    last_search_tql: string | null;
    last_tool_artifacts: Record<string, unknown>;
  };
}

export interface ThreadListPayload {
  status: string;
  threads: ThreadSummary[];
  surface: {
    status: string;
    reason: string;
    message: string;
  };
}

export interface ThreadStep {
  id: string;
  parent_id: string | null;
  name: string | null;
  type: string | null;
  input: string | null;
  output: string | null;
  is_error: boolean | null;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface ChatSuggestedAction {
  id: string;
  label: string;
  prompt: string;
}

export interface ThreadDetailPayload {
  status: string;
  thread: ThreadDetail | null;
  surface: {
    status: string;
    reason: string;
    message: string;
  };
}

export interface ThreadDetail {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  user_identifier: string | null;
  metadata: Record<string, unknown>;
  resume_context: {
    last_search_tql: string | null;
    last_search_params: Record<string, unknown>;
    last_tool_artifacts: Record<string, unknown>;
  };
  steps: ThreadStep[];
}

export interface ChatTurnInput {
  message: string;
  thread_id?: string | null;
  chat_profile?: string | null;
}

export interface ChatAssistantMessage {
  id: string | null;
  role: "assistant";
  content: string;
  created_at: string;
  status: "complete" | "error";
}

export type ChatStreamEvent =
  | {
      type: "thread";
      thread_id: string;
      chat_profile: string;
      profile_id: string | null;
    }
  | {
      type: "assistant_delta";
      thread_id: string;
      delta: string;
    }
  | {
      type: "assistant_message";
      thread_id: string;
      tool_calls: string[];
      suggested_actions?: ChatSuggestedAction[];
      message: ChatAssistantMessage;
    }
  | {
      type: "error";
      thread_id: string | null;
      error: string;
    };

export interface ChatTurnResult {
  thread_id: string | null;
  tool_calls: string[];
  suggested_actions?: ChatSuggestedAction[];
  message: ChatAssistantMessage;
}

export interface CompanySummary {
  id: string;
  company_uid: string;
  kbo_number: string | null;
  vat_number: string | null;
  name: string;
  city: string | null;
  status: string | null;
  industry: string | null;
  website_url: string | null;
  account_manager: string | null;
  open_tickets: number | null;
  exact_revenue_ytd: number | null;
  exact_outstanding: number | null;
  identity_link_status: string;
  linked_systems: string[];
  last_updated_at: string;
}

export interface CompanyListPayload {
  status: string;
  total: number;
  companies: CompanySummary[];
}

export interface CompanyDetailPayload {
  status: string;
  company: {
    company_uid: string;
    kbo_number: string | null;
    vat_number: string | null;
    name: string | null;
    city: string | null;
    legal_form: string | null;
    status: string | null;
    website_url: string | null;
    employee_count: number | null;
    nace_code: string | null;
    nace_description: string | null;
    identity_link_status: string;
    last_updated_at: string;
    linked_systems: string[];
  };
  sources: {
    teamleader: Record<string, unknown>;
    exact: Record<string, unknown>;
    autotask: Record<string, unknown>;
  };
  pipeline: Record<string, unknown>;
  financials: Record<string, unknown>;
  activity: Array<{
    source_system: string;
    activity_type: string;
    activity_description: string;
    activity_date: string;
    activity_data: Record<string, unknown>;
  }>;
}

export interface SegmentSummary {
  id: string;
  segment_key: string;
  name: string;
  description: string | null;
  owner: string | null;
  member_count: number;
  updated_at: string;
}

export interface SegmentListPayload {
  status: string;
  segments: SegmentSummary[];
}

export interface SegmentMemberPreview {
  id: string;
  kbo_number: string | null;
  vat_number: string | null;
  company_name: string | null;
  city: string | null;
  status: string | null;
  main_email?: string | null;
  main_phone?: string | null;
  website_url?: string | null;
}

export interface SegmentDetailPayload {
  status: string;
  segment: {
    segment_id: string;
    segment_key: string;
    segment_name: string;
    description: string | null;
    definition_type: string;
    definition_json: Record<string, unknown>;
    total_count: number;
    rows: SegmentMemberPreview[];
    backend: string;
  };
  stats: {
    profile_count?: number;
    contact_coverage?: {
      email_coverage_percent: number;
      phone_coverage_percent: number;
      profiles_with_email: number;
      profiles_with_phone: number;
    };
    top_cities?: Array<{ city: string; count: number }>;
    status_distribution?: Record<string, number>;
    juridical_form_distribution?: Record<string, number>;
  };
}

export interface CreateSegmentInput {
  name: string;
  description?: string;
  keywords?: string;
  city?: string;
  status?: string;
  has_email?: boolean;
  has_phone?: boolean;
  email_domain?: string;
}

export interface CreateSegmentResult {
  status: string;
  segment: {
    segment_id: string;
    segment_key: string;
    segment_name: string;
    member_count: number;
    backend: string;
  };
}

export interface SegmentExportResult {
  status: string;
  filename: string;
  exported_count: number;
  total_in_segment: number;
  download_url: string;
  backend: string;
}

export interface FeedbackAttachment {
  attachment_id: string;
  file_name: string;
  content_type?: string | null;
  byte_size: number;
  storage_path: string;
}

export interface FeedbackSubmissionInput {
  surface: string;
  feedbackText: string;
  pagePath?: string;
  pageUrl?: string;
  threadId?: string | null;
  companyRef?: string | null;
  segmentRef?: string | null;
  context?: Record<string, unknown>;
  screenshots?: File[];
}

export interface FeedbackSubmissionResult {
  status: "accepted";
  feedback_id: string;
  evaluation_status: string;
  notification_status: string;
  attachments: FeedbackAttachment[];
}

export interface MockSurfaceCard {
  title: string;
  eyebrow: string;
  detail: string;
  badges: string[];
  footer: string;
}

export interface MockSurfacePayload {
  title: string;
  detail: string;
  cards: MockSurfaceCard[];
}
