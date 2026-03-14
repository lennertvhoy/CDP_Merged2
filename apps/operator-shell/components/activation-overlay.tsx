import { useState, useEffect } from "react";
import { Loader2, CheckCircle2, AlertCircle, Send, Users, X } from "lucide-react";
import type { ActivationState } from "@/app/page";

export function ActivationOverlay({ 
  state, 
  onClose, 
  onChangeState 
}: { 
  state: ActivationState; 
  onClose: () => void;
  onChangeState: (newState: ActivationState) => void;
}) {
  if (!state || state === "idle") return null;

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-[480px] bg-[#0a0a0a] border border-zinc-800 rounded-xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800 bg-zinc-950/50">
          <div className="flex items-center gap-2.5">
            {state.includes("tracardi") ? (
              <div className="w-8 h-8 rounded-[6px] bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                <Users size={16} className="text-indigo-400" />
              </div>
            ) : (
              <div className="w-8 h-8 rounded-[6px] bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                <Send size={16} className="text-emerald-400" />
              </div>
            )}
            <div>
              <h3 className="text-sm font-medium text-zinc-100">
                {state.includes("tracardi") ? "Sync to Tracardi" : "Send via Resend"}
              </h3>
              <p className="text-[11px] font-mono text-zinc-500">
                {state.includes("tracardi") ? "CDP Activation" : "Email Outreach"}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300 transition-colors p-1">
            <X size={16} />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 flex flex-col gap-6">
          {state === "syncing_tracardi" && (
            <SyncingTracardi onComplete={() => onChangeState("sync_tracardi_success")} />
          )}
          {state === "sync_tracardi_success" && (
            <SyncTracardiSuccess onClose={onClose} />
          )}
          {state === "resend_audience" && (
            <ResendAudienceSelection onNext={() => onChangeState("resend_sending")} />
          )}
          {state === "resend_sending" && (
            <ResendSending onComplete={() => onChangeState("resend_success")} />
          )}
          {state === "resend_success" && (
            <ResendSuccess onClose={onClose} />
          )}
        </div>
      </div>
    </div>
  );
}

function SyncingTracardi({ onComplete }: { onComplete: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onComplete, 2500);
    return () => clearTimeout(timer);
  }, [onComplete]);

  return (
    <div className="flex flex-col items-center justify-center py-8 gap-4">
      <Loader2 size={32} className="text-indigo-500 animate-spin" />
      <div className="flex flex-col items-center gap-1">
        <span className="text-sm font-medium text-zinc-200">Syncing 14 profiles to Tracardi...</span>
        <span className="text-xs font-mono text-zinc-500">Mapping Exact & Autotask fields</span>
      </div>
      
      <div className="w-full max-w-[240px] mt-4">
        <div className="h-1.5 w-full bg-zinc-900 rounded-full overflow-hidden">
          <div className="h-full bg-indigo-500 w-2/3 animate-pulse rounded-full"></div>
        </div>
      </div>
    </div>
  );
}

function SyncTracardiSuccess({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-6 gap-5">
      <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center">
        <CheckCircle2 size={24} className="text-emerald-500" />
      </div>
      <div className="flex flex-col items-center gap-1 text-center">
        <span className="text-base font-medium text-zinc-100">Sync Complete</span>
        <span className="text-sm text-zinc-400">14 profiles successfully updated in Tracardi.</span>
      </div>
      
      <div className="w-full bg-zinc-900/50 border border-zinc-800 rounded-lg p-3 flex flex-col gap-2 mt-2">
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Target Segment</span>
          <span className="font-mono text-zinc-300">Tech_Enterprise_Active</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Profiles Created</span>
          <span className="font-mono text-zinc-300">2</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Profiles Updated</span>
          <span className="font-mono text-zinc-300">12</span>
        </div>
      </div>

      <button 
        onClick={onClose}
        className="mt-2 w-full py-2 bg-zinc-100 hover:bg-white text-zinc-900 text-sm font-medium rounded-[6px] transition-colors"
      >
        Done
      </button>
    </div>
  );
}

function ResendAudienceSelection({ onNext }: { onNext: () => void }) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium text-zinc-200">Review Audience</span>
        <span className="text-xs text-zinc-500">14 companies selected. 1 company has active support tickets.</span>
      </div>

      <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 flex gap-3">
        <AlertCircle size={16} className="text-amber-500 shrink-0 mt-0.5" />
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-amber-500">Support Risk Detected</span>
          <span className="text-xs text-amber-500/80">
            CyberSec Partners has 1 open ticket. Sending marketing emails during active support resolution may cause friction.
          </span>
        </div>
      </div>

      <div className="flex flex-col gap-3 mt-2">
        <label className="flex items-center gap-3 p-3 border border-zinc-800 rounded-lg cursor-pointer hover:bg-zinc-900/50 transition-colors">
          <input type="radio" name="audience" defaultChecked className="accent-emerald-500" />
          <div className="flex flex-col">
            <span className="text-sm font-medium text-zinc-200">Safe Send (Recommended)</span>
            <span className="text-xs text-zinc-500">Exclude 1 company with open tickets. Send to 13.</span>
          </div>
        </label>
        <label className="flex items-center gap-3 p-3 border border-zinc-800 rounded-lg cursor-pointer hover:bg-zinc-900/50 transition-colors">
          <input type="radio" name="audience" className="accent-emerald-500" />
          <div className="flex flex-col">
            <span className="text-sm font-medium text-zinc-200">Force Send All</span>
            <span className="text-xs text-zinc-500">Send to all 14 companies regardless of ticket status.</span>
          </div>
        </label>
      </div>

      <div className="flex justify-end gap-3 mt-4">
        <button className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-zinc-200 transition-colors">
          Cancel
        </button>
        <button 
          onClick={onNext}
          className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-emerald-950 text-sm font-medium rounded-[6px] transition-colors flex items-center gap-2"
        >
          <Send size={14} />
          Send Campaign
        </button>
      </div>
    </div>
  );
}

function ResendSending({ onComplete }: { onComplete: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onComplete, 2000);
    return () => clearTimeout(timer);
  }, [onComplete]);

  return (
    <div className="flex flex-col items-center justify-center py-8 gap-4">
      <Loader2 size={32} className="text-emerald-500 animate-spin" />
      <div className="flex flex-col items-center gap-1">
        <span className="text-sm font-medium text-zinc-200">Dispatching via Resend...</span>
        <span className="text-xs font-mono text-zinc-500">Sending to 13 recipients</span>
      </div>
    </div>
  );
}

function ResendSuccess({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-6 gap-5">
      <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center">
        <CheckCircle2 size={24} className="text-emerald-500" />
      </div>
      <div className="flex flex-col items-center gap-1 text-center">
        <span className="text-base font-medium text-zinc-100">Campaign Dispatched</span>
        <span className="text-sm text-zinc-400">Emails successfully queued in Resend.</span>
      </div>
      
      <div className="w-full bg-zinc-900/50 border border-zinc-800 rounded-lg p-3 flex flex-col gap-2 mt-2">
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Total Sent</span>
          <span className="font-mono text-zinc-300">13</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Excluded (Support Risk)</span>
          <span className="font-mono text-amber-400">1</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Campaign ID</span>
          <span className="font-mono text-zinc-300">cmp_8f92a7</span>
        </div>
      </div>

      <button 
        onClick={onClose}
        className="mt-2 w-full py-2 bg-zinc-100 hover:bg-white text-zinc-900 text-sm font-medium rounded-[6px] transition-colors"
      >
        Done
      </button>
    </div>
  );
}
