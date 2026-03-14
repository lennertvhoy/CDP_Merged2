"use client";

import { useState } from "react";
import { SegmentGrid } from "./segment-grid";
import { CompanySidePanel } from "./company-side-panel";
import { LayoutGrid, Maximize2, RefreshCw } from "lucide-react";
import { ActivationOverlay } from "./activation-overlay";
import type { ActivationState } from "@/app/page";

export function DataCanvas({ 
  activationState, 
  onActivationClose, 
  onActivationChange 
}: { 
  activationState?: ActivationState;
  onActivationClose?: () => void;
  onActivationChange?: (state: ActivationState) => void;
}) {
  const [selectedEntity, setSelectedEntity] = useState<string | null>("BE0412345678");

  return (
    <div className="flex-1 flex flex-col bg-[#050505] relative z-0 overflow-hidden">
      {/* Activation Overlay */}
      {activationState && onActivationClose && onActivationChange && (
        <ActivationOverlay 
          state={activationState} 
          onClose={onActivationClose} 
          onChangeState={onActivationChange} 
        />
      )}

      {/* Canvas Header */}
      <div className="h-12 border-b border-zinc-800 flex items-center px-6 justify-between shrink-0 bg-zinc-950/50 backdrop-blur-sm z-10">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm font-medium text-zinc-100">
            <LayoutGrid size={14} className="text-zinc-500" />
            <span>Data Canvas</span>
          </div>
          <div className="h-4 w-px bg-zinc-800"></div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-zinc-500 px-1.5 py-0.5 bg-zinc-900 border border-zinc-800 rounded-[4px]">
              Mode: SEGMENT_BUILDER
            </span>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-[10px] font-mono text-zinc-500">
            <RefreshCw size={10} />
            Canvas rendered: 10:42 AM
          </div>
          <button className="text-zinc-500 hover:text-zinc-300 p-1">
            <Maximize2 size={14} />
          </button>
        </div>
      </div>

      {/* Canvas Content Area */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Main Grid */}
        <div className={`flex-1 overflow-y-auto p-6 transition-all duration-300 ${selectedEntity ? 'mr-[420px]' : ''}`}>
          <div className="w-full mx-auto">
            <SegmentGrid 
              onRowClick={(id) => setSelectedEntity(id)} 
              activeRow={selectedEntity} 
            />
          </div>
        </div>

        {/* Slide-over Side Panel */}
        <div 
          className={`absolute top-0 right-0 bottom-0 w-[420px] bg-[#0a0a0a] border-l border-zinc-800 shadow-2xl transform transition-transform duration-300 ease-in-out z-20 ${
            selectedEntity ? 'translate-x-0' : 'translate-x-full'
          }`}
        >
          {selectedEntity && (
            <CompanySidePanel 
              entityId={selectedEntity} 
              onClose={() => setSelectedEntity(null)} 
            />
          )}
        </div>
      </div>
    </div>
  );
}
