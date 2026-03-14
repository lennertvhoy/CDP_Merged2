import { useState } from "react";
import { Settings, User, Shield, Bell, Key, Loader2, AlertTriangle } from "lucide-react";
import { StateSwitcher, type ViewState } from "./state-switcher";

export function SettingsView() {
  const [viewState, setViewState] = useState<ViewState>("success");

  return (
    <div className="flex-1 flex flex-col bg-[#050505] overflow-hidden">
      {/* Header */}
      <div className="h-16 border-b border-zinc-800 flex items-center px-8 justify-between shrink-0 bg-zinc-950/50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-[6px] bg-zinc-800/50 border border-zinc-700 flex items-center justify-center">
            <Settings size={16} className="text-zinc-400" />
          </div>
          <h1 className="text-lg font-medium text-zinc-100">Settings</h1>
        </div>
        <div className="flex items-center gap-4">
          <StateSwitcher currentState={viewState} onStateChange={setViewState} />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-5xl mx-auto flex gap-12">
          
          {/* Sidebar Menu */}
          <div className="w-64 flex flex-col gap-2 shrink-0">
            <button className="flex items-center gap-3 px-4 py-2.5 rounded-[8px] bg-zinc-900 text-zinc-100 font-medium text-sm transition-colors">
              <User size={16} className="text-zinc-400" />
              Profile & Account
            </button>
            <button className="flex items-center gap-3 px-4 py-2.5 rounded-[8px] text-zinc-500 hover:bg-zinc-900/50 hover:text-zinc-300 font-medium text-sm transition-colors">
              <Shield size={16} className="text-zinc-400" />
              Team & Roles
            </button>
            <button className="flex items-center gap-3 px-4 py-2.5 rounded-[8px] text-zinc-500 hover:bg-zinc-900/50 hover:text-zinc-300 font-medium text-sm transition-colors">
              <Key size={16} className="text-zinc-400" />
              API Keys
            </button>
            <button className="flex items-center gap-3 px-4 py-2.5 rounded-[8px] text-zinc-500 hover:bg-zinc-900/50 hover:text-zinc-300 font-medium text-sm transition-colors">
              <Bell size={16} className="text-zinc-400" />
              Notifications
            </button>
          </div>

          {/* Main Settings Area */}
          <div className="flex-1 flex flex-col gap-8">
            
            {viewState === "loading" && (
              <div className="flex flex-col items-center justify-center py-24 text-zinc-500">
                <Loader2 size={24} className="animate-spin mb-4 text-zinc-400" />
                <p className="text-sm font-medium">Loading settings...</p>
              </div>
            )}

            {viewState === "error" && (
              <div className="flex flex-col items-center justify-center py-24 text-zinc-500 border border-zinc-800 rounded-[8px] bg-rose-500/5">
                <AlertTriangle size={32} className="mb-4 text-rose-500" />
                <p className="text-sm font-medium text-rose-400">Failed to load settings</p>
                <p className="text-xs mt-1 max-w-sm text-center text-zinc-400">There was an error retrieving your account information. Please try again.</p>
                <button className="mt-6 bg-zinc-900 border border-zinc-700 hover:bg-zinc-800 text-zinc-300 px-4 py-2 text-sm font-medium rounded-[6px] transition-colors">
                  Retry
                </button>
              </div>
            )}

            {(viewState === "success" || viewState === "partial" || viewState === "empty") && (
              <>
                <div className="flex flex-col gap-2">
                  <h2 className="text-xl font-medium text-zinc-100">Profile & Account</h2>
                  <p className="text-sm text-zinc-500">Manage your personal information and preferences.</p>
                </div>

                <div className="bg-[#0a0a0a] border border-zinc-800 rounded-xl p-6 flex flex-col gap-6">
                  
                  {viewState === "partial" && (
                    <div className="bg-amber-500/10 border border-amber-500/20 rounded-[6px] p-3 flex items-start gap-3 text-sm mb-2">
                      <AlertTriangle size={16} className="text-amber-500 mt-0.5 shrink-0" />
                      <div>
                        <p className="text-amber-400 font-medium">Read-only mode</p>
                        <p className="text-amber-500/70 mt-0.5">We couldn't verify your write permissions. Changes cannot be saved right now.</p>
                      </div>
                    </div>
                  )}

                  <div className="flex items-center gap-6">
                    <div className="w-20 h-20 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-2xl font-medium text-zinc-400">
                      LV
                    </div>
                    <div className="flex flex-col gap-2">
                      <button 
                        className="px-4 py-2 bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 text-zinc-300 text-sm font-medium rounded-[6px] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={viewState === "partial"}
                      >
                        Upload Avatar
                      </button>
                      <span className="text-xs text-zinc-500">JPG, GIF or PNG. Max size of 800K.</span>
                    </div>
                  </div>

                  <div className="w-full h-px bg-zinc-800/50"></div>

                  <div className="grid grid-cols-2 gap-6">
                    <div className="flex flex-col gap-2">
                      <label className="text-sm font-medium text-zinc-300">Full Name</label>
                      <input 
                        type="text" 
                        defaultValue="Lennert Van Hoyweghen" 
                        disabled={viewState === "partial"}
                        className="bg-zinc-900 border border-zinc-800 rounded-[6px] py-2 px-3 text-sm text-zinc-100 focus:outline-none focus:border-zinc-600 disabled:opacity-50 disabled:cursor-not-allowed" 
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <label className="text-sm font-medium text-zinc-300">Email Address</label>
                      <input 
                        type="email" 
                        defaultValue="lennertvhoy@gmail.com" 
                        disabled={viewState === "partial"}
                        className="bg-zinc-900 border border-zinc-800 rounded-[6px] py-2 px-3 text-sm text-zinc-100 focus:outline-none focus:border-zinc-600 disabled:opacity-50 disabled:cursor-not-allowed" 
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <label className="text-sm font-medium text-zinc-300">Role</label>
                      <input 
                        type="text" 
                        defaultValue="Admin" 
                        disabled 
                        className="bg-zinc-900/50 border border-zinc-800/50 rounded-[6px] py-2 px-3 text-sm text-zinc-500 cursor-not-allowed" 
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <label className="text-sm font-medium text-zinc-300">Timezone</label>
                      <select 
                        disabled={viewState === "partial"}
                        className="bg-zinc-900 border border-zinc-800 rounded-[6px] py-2 px-3 text-sm text-zinc-100 focus:outline-none focus:border-zinc-600 appearance-none disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <option>Europe/Brussels (CET)</option>
                        <option>Europe/London (GMT)</option>
                        <option>America/New_York (EST)</option>
                      </select>
                    </div>
                  </div>

                  <div className="flex justify-end mt-4">
                    <button 
                      className="bg-emerald-500 hover:bg-emerald-400 text-emerald-950 px-6 py-2 text-sm font-medium rounded-[6px] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      disabled={viewState === "partial"}
                    >
                      Save Changes
                    </button>
                  </div>

                </div>
              </>
            )}

          </div>

        </div>
      </div>
    </div>
  );
}
