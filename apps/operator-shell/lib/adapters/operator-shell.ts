import { operatorClient } from "@/lib/api/operator-client";
import { mockSurfaceData } from "@/lib/mocks/operator-shell";
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
  MockSurfacePayload,
  SegmentDetailPayload,
  SegmentExportResult,
  SegmentListPayload,
  ThreadDetailPayload,
  ThreadListPayload,
} from "@/lib/types/operator";

export interface OperatorShellAdapter {
  getBootstrap(): Promise<BootstrapPayload>;
  login(username: string, password: string): Promise<LoginResult>;
  logout(): Promise<{ status: string }>;
  streamChatTurn(payload: ChatTurnInput): AsyncGenerator<ChatStreamEvent, void, undefined>;
  sendChatTurn(payload: ChatTurnInput): Promise<ChatTurnResult>;
  getThreads(search: string): Promise<ThreadListPayload>;
  getThread(threadId: string): Promise<ThreadDetailPayload>;
  getCompanies(params: { query: string; city: string; status: string }): Promise<CompanyListPayload>;
  getCompany(companyRef: string): Promise<CompanyDetailPayload>;
  getSegments(search: string): Promise<SegmentListPayload>;
  getSegment(segmentRef: string): Promise<SegmentDetailPayload>;
  createSegment(payload: CreateSegmentInput): Promise<CreateSegmentResult>;
  exportSegment(segmentRef: string): Promise<SegmentExportResult>;
  submitFeedback(payload: FeedbackSubmissionInput): Promise<FeedbackSubmissionResult>;
  getMockSurface(kind: "sources" | "pipelines" | "activity" | "settings"): Promise<MockSurfacePayload>;
}

class HybridOperatorShellAdapter implements OperatorShellAdapter {
  async getBootstrap() {
    return operatorClient.getBootstrap();
  }

  async login(username: string, password: string) {
    return operatorClient.login(username, password);
  }

  async logout() {
    return operatorClient.logout();
  }

  streamChatTurn(payload: ChatTurnInput) {
    return operatorClient.streamChatTurn(payload);
  }

  async sendChatTurn(payload: ChatTurnInput) {
    return operatorClient.sendChatTurn(payload);
  }

  async getThreads(search: string) {
    return operatorClient.getThreads(search);
  }

  async getThread(threadId: string) {
    return operatorClient.getThread(threadId);
  }

  async getCompanies(params: { query: string; city: string; status: string }) {
    return operatorClient.getCompanies(params);
  }

  async getCompany(companyRef: string) {
    return operatorClient.getCompany(companyRef);
  }

  async getSegments(search: string) {
    return operatorClient.getSegments(search);
  }

  async getSegment(segmentRef: string) {
    return operatorClient.getSegment(segmentRef);
  }

  async createSegment(payload: CreateSegmentInput) {
    return operatorClient.createSegment(payload);
  }

  async exportSegment(segmentRef: string) {
    return operatorClient.exportSegment(segmentRef);
  }

  async submitFeedback(payload: FeedbackSubmissionInput) {
    return operatorClient.submitFeedback(payload);
  }

  async getMockSurface(kind: "sources" | "pipelines" | "activity" | "settings") {
    return mockSurfaceData[kind];
  }
}

export const operatorShellAdapter: OperatorShellAdapter = new HybridOperatorShellAdapter();
