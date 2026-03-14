"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { AccessGate } from "@/components/access-gate";
import { ChatSurface } from "@/components/chat-surface";
import { CompaniesSurface } from "@/components/companies-surface";
import { MockSurface } from "@/components/mock-surface";
import { SegmentsSurface } from "@/components/segments-surface";
import { SessionBar } from "@/components/session-bar";
import { Sidebar } from "@/components/sidebar";
import { ThreadsSurface } from "@/components/threads-surface";
import { ErrorState } from "@/components/shell-primitives";
import { operatorShellAdapter } from "@/lib/adapters/operator-shell";
import { initialsFromName } from "@/lib/formatters";
import type { BootstrapPayload, TabId, ThreadDetail } from "@/lib/types/operator";

const adapter = operatorShellAdapter;

export function OperatorShellApp() {
  const [activeTab, setActiveTab] = useState<TabId>("chat");
  const [bootstrap, setBootstrap] = useState<BootstrapPayload | null>(null);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [resumeThread, setResumeThread] = useState<ThreadDetail | null>(null);
  const [mockSurface, setMockSurface] = useState<Awaited<
    ReturnType<typeof adapter.getMockSurface>
  > | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setBootstrapError(null);

    void adapter
      .getBootstrap()
      .then((result) => {
        if (active) {
          setBootstrap(result);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setBootstrapError(
            reason instanceof Error ? reason.message : "Failed to load operator bootstrap.",
          );
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!["sources", "pipelines", "activity", "settings"].includes(activeTab)) {
      return;
    }

    let active = true;
    const mockTab = activeTab as "sources" | "pipelines" | "activity" | "settings";

    void adapter.getMockSurface(mockTab).then((payload) => {
      if (active) {
        setMockSurface(payload);
      }
    });

    return () => {
      active = false;
    };
  }, [activeTab]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950 text-zinc-500">
        <div className="flex items-center gap-3 rounded-2xl border border-zinc-800 bg-zinc-900/70 px-5 py-4">
          <Loader2 size={18} className="animate-spin" />
          Loading private preview...
        </div>
      </div>
    );
  }

  if (bootstrapError || !bootstrap) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950 px-6">
        <div className="w-full max-w-3xl">
          <ErrorState
            title="Unable to open the preview"
            detail={
              bootstrapError || "The preview could not be loaded right now."
            }
          />
        </div>
      </div>
    );
  }

  async function refreshBootstrap() {
    setBootstrapError(null);
    try {
      const result = await adapter.getBootstrap();
      setBootstrap(result);
      if (!result.session.authenticated) {
        setResumeThread(null);
      }
    } catch (reason) {
      setBootstrapError(
        reason instanceof Error ? reason.message : "Failed to load operator bootstrap.",
      );
    }
  }

  if (bootstrap.phase === "access_gate") {
    return <AccessGate adapter={adapter} session={bootstrap.session} onSessionChanged={refreshBootstrap} />;
  }

  const displayName =
    bootstrap.session.user?.display_name || bootstrap.session.user?.identifier || "CDP";
  const authStateKey =
    bootstrap.session.user?.identifier || (bootstrap.session.authenticated ? "authenticated" : "preview");

  function handleResumeThread(thread: ThreadDetail) {
    setResumeThread(thread);
    setActiveTab("chat");
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-zinc-950">
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        userInitials={initialsFromName(displayName)}
        adapter={adapter}
      />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <SessionBar adapter={adapter} session={bootstrap.session} onSessionChanged={refreshBootstrap} />

        {activeTab === "chat" ? (
          <ChatSurface adapter={adapter} bootstrap={bootstrap} resumeThread={resumeThread} />
        ) : null}
        {activeTab === "threads" ? (
          <ThreadsSurface
            adapter={adapter}
            surface={bootstrap.surfaces!.threads}
            authKey={authStateKey}
            onResumeThread={handleResumeThread}
          />
        ) : null}
        {activeTab === "companies" ? (
          <CompaniesSurface adapter={adapter} surface={bootstrap.surfaces!.companies} />
        ) : null}
        {activeTab === "segments" ? (
          <SegmentsSurface adapter={adapter} surface={bootstrap.surfaces!.segments} />
        ) : null}
        {activeTab === "sources" && mockSurface ? <MockSurface payload={mockSurface} /> : null}
        {activeTab === "pipelines" && mockSurface ? <MockSurface payload={mockSurface} /> : null}
        {activeTab === "activity" && mockSurface ? <MockSurface payload={mockSurface} /> : null}
        {activeTab === "settings" && mockSurface ? <MockSurface payload={mockSurface} /> : null}
      </div>
    </div>
  );
}
