"use client";

import { Send, Terminal, ChevronDown } from "lucide-react";
import type { ActivationState } from "@/app/page";

export function ChatShell({ onActionSelect }: { onActionSelect?: (state: ActivationState) => void }) {
  return (
    <div className="w-[400px] flex-shrink-0 border-r border-zinc-800 bg-[#0a0a0a] flex flex-col z-10">
      {/* Header */}
      <div className="h-12 border-b border-zinc-800 flex items-center px-4 justify-between shrink-0">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
          <Terminal size={14} className="text-zinc-500" />
          <span>Operator Shell</span>
        </div>
        <button className="text-zinc-500 hover:text-zinc-300 flex items-center gap-1 text-xs font-mono">
          Thread: 8f92a <ChevronDown size={12} />
        </button>
      </div>

      {/* Chat Feed */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-6">
        <Message 
          role="user" 
          content="Toon mij alle actieve Enterprise klanten in de tech sector met Exact-omzet en minstens 1 open ticket." 
        />
        <Message 
          role="system" 
          content="Querying PostgreSQL for active tech enterprises with Exact revenue and open tickets..." 
          isLoading 
        />
        <Message 
          role="system" 
          content="Ik heb de PostgreSQL database bevraagd. Er zijn 14 bedrijven gevonden die aan deze criteria voldoen. Het gestructureerde segment is geladen in het Data Canvas." 
          hasAction
          chips={["Export CSV", "Sync to Tracardi", "Send via Resend"]}
          onActionSelect={onActionSelect}
        />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-zinc-800 bg-zinc-950 shrink-0">
        <div className="relative flex items-center">
          <input 
            type="text" 
            placeholder="Query data, create segments, or ask questions..." 
            className="w-full bg-zinc-900 border border-zinc-800 rounded-[4px] py-2.5 pl-3 pr-10 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-600 focus:ring-1 focus:ring-zinc-600 transition-all font-sans"
            defaultValue="Toon mij alle actieve Enterprise klanten in de tech sector met Exact-omzet en minstens 1 open ticket."
          />
          <button className="absolute right-2 text-zinc-500 hover:text-zinc-300 p-1">
            <Send size={16} />
          </button>
        </div>
        <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-zinc-600">
          <span>PostgreSQL: Connected</span>
          <span>Press Enter to execute</span>
        </div>
      </div>
    </div>
  );
}

function Message({ role, content, isLoading, hasAction, chips, onActionSelect }: { role: "user" | "system", content: string, isLoading?: boolean, hasAction?: boolean, chips?: string[], onActionSelect?: (state: ActivationState) => void }) {
  if (role === "user") {
    return (
      <div className="flex flex-col items-end gap-1">
        <div className="bg-zinc-800 text-zinc-100 px-3 py-2 rounded-[4px] text-sm max-w-[90%]">
          {content}
        </div>
        <span className="text-[10px] font-mono text-zinc-600">10:42 AM</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <div className="flex items-start gap-2 max-w-[95%]">
        <div className="w-6 h-6 rounded-[4px] bg-zinc-900 border border-zinc-800 flex items-center justify-center shrink-0 mt-0.5">
          <Terminal size={12} className="text-zinc-400" />
        </div>
        <div className="flex flex-col gap-2">
          <div className={`text-sm ${isLoading ? 'text-zinc-500 font-mono text-xs' : 'text-zinc-300'}`}>
            {content}
          </div>
          {hasAction && (
            <div className="flex items-center gap-2 mt-1">
              <button className="text-xs font-mono bg-zinc-900 border border-zinc-700 hover:bg-zinc-800 text-zinc-300 px-2 py-1 rounded-[4px] transition-colors">
                Review Segment
              </button>
            </div>
          )}
          {chips && (
            <div className="flex flex-wrap gap-2 mt-2">
              {chips.map(chip => (
                <button 
                  key={chip} 
                  onClick={() => {
                    if (chip === "Sync to Tracardi" && onActionSelect) onActionSelect("syncing_tracardi");
                    if (chip === "Send via Resend" && onActionSelect) onActionSelect("resend_audience");
                  }}
                  className="text-[11px] bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 text-zinc-400 px-2.5 py-1.5 rounded-[4px] transition-colors"
                >
                  {chip}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
