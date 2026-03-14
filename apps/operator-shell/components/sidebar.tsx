import {
  Activity,
  Building2,
  Database,
  GitBranch,
  MessageSquare,
  MessageSquareWarning,
  Settings,
  TerminalSquare,
  Users,
} from "lucide-react";
import type { TabId } from "@/lib/types/operator";
import type { OperatorShellAdapter } from "@/lib/adapters/operator-shell";
import { FeedbackButton } from "./feedback-button";

export function Sidebar({
  activeTab,
  onTabChange,
  userInitials,
  adapter,
}: {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  userInitials: string;
  adapter: OperatorShellAdapter;
}) {
  return (
    <div className="w-16 flex-shrink-0 border-r border-zinc-800 bg-zinc-950 flex flex-col items-center py-4 gap-6 z-10">
      <div className="w-8 h-8 bg-zinc-100 text-zinc-900 flex items-center justify-center rounded-[4px] font-mono font-bold text-xs">
        CDP
      </div>
      
      <nav className="flex flex-col gap-4 flex-1 w-full items-center mt-4">
        <NavItem icon={<TerminalSquare size={18} />} label="Chat" active={activeTab === "chat"} onClick={() => onTabChange("chat")} />
        <NavItem icon={<MessageSquare size={18} />} label="Threads" active={activeTab === "threads"} onClick={() => onTabChange("threads")} />
        <NavItem icon={<Building2 size={18} />} label="Companies" active={activeTab === "companies"} onClick={() => onTabChange("companies")} />
        <NavItem icon={<Users size={18} />} label="Segments" active={activeTab === "segments"} onClick={() => onTabChange("segments")} />
        <NavItem icon={<Database size={18} />} label="Sources" active={activeTab === "sources"} onClick={() => onTabChange("sources")} />
        <NavItem icon={<GitBranch size={18} />} label="Pipelines" active={activeTab === "pipelines"} onClick={() => onTabChange("pipelines")} />
        <NavItem icon={<Activity size={18} />} label="Activity" active={activeTab === "activity"} onClick={() => onTabChange("activity")} />
      </nav>

      <div className="mt-auto flex flex-col gap-4 w-full items-center">
        <FeedbackButton
          adapter={adapter}
          surface="global"
          buttonLabel=""
          buttonClassName="w-10 h-10 flex items-center justify-center rounded-[6px] transition-colors text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900"
        />
        <NavItem icon={<Settings size={18} />} label="Settings" active={activeTab === "settings"} onClick={() => onTabChange("settings")} />
        <div className="w-8 h-8 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-xs font-medium text-zinc-400">
          {userInitials}
        </div>
      </div>
    </div>
  );
}

function NavItem({ icon, label, active = false, onClick }: { icon: React.ReactNode; label: string; active?: boolean; onClick?: () => void }) {
  return (
    <button 
      onClick={onClick}
      className={`w-10 h-10 flex items-center justify-center rounded-[6px] transition-colors ${
        active ? "bg-zinc-800 text-zinc-100" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900"
      }`}
      title={label}
    >
      {icon}
    </button>
  );
}
