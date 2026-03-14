import type { MockSurfacePayload } from "@/lib/types/operator";

export const mockSurfaceData: Record<
  "sources" | "pipelines" | "activity" | "settings",
  MockSurfacePayload
> = {
  sources: {
    title: "Sources",
    detail:
      "These status cards are still mocked because the operator shell does not have a stable source-health API yet.",
    cards: [
      {
        title: "Exact Online",
        eyebrow: "Mocked health card",
        detail: "Finance sync appears healthy in the shell, but this card is not bound to a verified operator API yet.",
        badges: ["Mocked", "Future backend route", "Do not trust for ops"],
        footer: "Real financial facts still come from PostgreSQL-backed company and segment routes.",
      },
      {
        title: "Teamleader",
        eyebrow: "Mocked health card",
        detail: "CRM linkage is represented visually here, but status comes from adapter mock data in this pass.",
        badges: ["Mocked", "No source-status endpoint"],
        footer: "Use company 360 and canonical segments for authoritative colleague-facing answers.",
      },
      {
        title: "Autotask / Resend",
        eyebrow: "Mocked health card",
        detail: "Workflow/runtime status remains incomplete or environment-dependent for operator use.",
        badges: ["Mocked", "Blocked runtime parity"],
        footer: "This stays explicit instead of pretending Tracardi/community runtime parity exists.",
      },
    ],
  },
  pipelines: {
    title: "Pipelines",
    detail:
      "Pipeline cards remain mocked because workflow runtime states are not yet exposed as a stable operator surface.",
    cards: [
      {
        title: "Daily Segment Projection",
        eyebrow: "Mocked workflow",
        detail: "Represents the future Tracardi/activation shell, but does not claim live execution parity.",
        badges: ["Mocked", "CE limitation aware"],
        footer: "PostgreSQL remains the truth layer; activation runtime stays explicitly secondary.",
      },
      {
        title: "Support-Friction Pause",
        eyebrow: "Mocked workflow",
        detail: "Shows intended operator behavior without asserting that every runtime action is currently wired.",
        badges: ["Mocked", "No live action route"],
        footer: "This is preserved as design intent, not backend truth.",
      },
      {
        title: "Resend Broadcast Trigger",
        eyebrow: "Mocked workflow",
        detail: "Resend is represented here, but send/sync actions are not bound to the shell yet.",
        badges: ["Mocked", "Future bridge"],
        footer: "Only CSV export and canonical segment retrieval are real in this pass.",
      },
    ],
  },
  activity: {
    title: "Activity",
    detail:
      "Activity and audit remain mocked until a stable operator-safe feed exists that does not blur demo evidence with runtime truth.",
    cards: [
      {
        title: "Prompt Run",
        eyebrow: "Mocked audit line",
        detail: "A believable operator event, but not backed by a verified API yet.",
        badges: ["Mocked", "Audit feed pending"],
        footer: "No fake-solid audit claims were added for this screen.",
      },
      {
        title: "Segment Sync",
        eyebrow: "Mocked audit line",
        detail: "Sync feedback is intentionally not treated as authoritative until backend evidence exists.",
        badges: ["Mocked", "Not authoritative"],
        footer: "Real segment membership remains PostgreSQL-first.",
      },
      {
        title: "Broadcast Send",
        eyebrow: "Mocked audit line",
        detail: "Activation outcomes are shown as shell placeholders only.",
        badges: ["Mocked", "Future integration"],
        footer: "This avoids pretending the operator shell already owns delivery truth.",
      },
    ],
  },
  settings: {
    title: "Settings",
    detail:
      "Settings stay mocked in this pass so the new shell does not invent a second auth, profile, or ownership surface.",
    cards: [
      {
        title: "Profile & Account",
        eyebrow: "Mocked account panel",
        detail: "The UI is staged for colleague-facing use, but identity remains backend-managed.",
        badges: ["Mocked", "No second auth model"],
        footer: "Authentication truth still lives with the current Python runtime.",
      },
      {
        title: "Roles & Access",
        eyebrow: "Mocked account panel",
        detail: "Role controls are deliberately nonfunctional until real backend ownership rules are exposed here.",
        badges: ["Mocked", "Ownership preserved"],
        footer: "Thread ownership remains authoritative in app_chat tables and existing auth paths.",
      },
      {
        title: "Notifications / Keys",
        eyebrow: "Mocked account panel",
        detail: "Admin controls remain placeholders rather than fake production settings.",
        badges: ["Mocked", "Out of scope"],
        footer: "No Azure or local-secret coupling was introduced for the shell.",
      },
    ],
  },
};
