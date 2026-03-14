import { OperatorShellApp } from "@/components/operator-shell-app";
export type { TabId } from "@/lib/types/operator";

export type ActivationState =
  | "idle"
  | "syncing_tracardi"
  | "sync_tracardi_success"
  | "sync_tracardi_failed"
  | "resend_audience"
  | "resend_sending"
  | "resend_success"
  | null;

export default function Page() {
  return <OperatorShellApp />;
}
