import { useState } from "react";
import { Settings2 } from "lucide-react";

export type ViewState = "success" | "loading" | "empty" | "error" | "partial";

export function StateSwitcher({ 
  currentState, 
  onStateChange 
}: { 
  currentState: ViewState; 
  onStateChange: (state: ViewState) => void;
}) {
  return (
    <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-[6px] p-1">
      <Settings2 size={14} className="text-zinc-500 ml-2" />
      <div className="h-3 w-px bg-zinc-800 mx-1"></div>
      {(["success", "loading", "empty", "error", "partial"] as ViewState[]).map((state) => (
        <button
          key={state}
          onClick={() => onStateChange(state)}
          className={`px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider rounded-[4px] transition-colors ${
            currentState === state 
              ? "bg-zinc-800 text-zinc-100" 
              : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
          }`}
        >
          {state}
        </button>
      ))}
    </div>
  );
}
