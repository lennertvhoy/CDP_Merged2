"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shield, Users, Loader2, AlertTriangle, ArrowLeft } from "lucide-react";

interface User {
  account_id: string;
  identifier: string;
  display_name: string | null;
  is_admin: boolean;
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
}

export default function AdminPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [bootstrap, setBootstrap] = useState<any>(null);

  useEffect(() => {
    async function load() {
      try {
        // First check bootstrap to verify admin status
        const bootstrapRes = await fetch("/operator-api/bootstrap");
        const bootstrapData = await bootstrapRes.json();
        setBootstrap(bootstrapData);

        if (bootstrapData.phase === "access_gate") {
          setError("Please sign in to access the admin panel.");
          setLoading(false);
          return;
        }

        const isUserAdmin = bootstrapData.session?.user?.is_admin === true;
        setIsAdmin(isUserAdmin);

        if (!isUserAdmin) {
          setError("You do not have admin privileges.");
          setLoading(false);
          return;
        }

        // Load users list
        const response = await fetch("/operator-api/admin/users");
        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: "Failed to load users" }));
          throw new Error(err.detail || `HTTP ${response.status}`);
        }
        const data = await response.json();
        setUsers(data.users || []);
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load admin panel");
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-zinc-500">
          <Loader2 size={32} className="animate-spin" />
          <p className="text-sm">Loading admin panel...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-rose-500/5 border border-rose-500/20 rounded-xl p-6">
          <div className="flex items-start gap-4">
            <AlertTriangle size={24} className="text-rose-500 shrink-0 mt-0.5" />
            <div>
              <h2 className="text-rose-400 font-medium mb-1">Access Denied</h2>
              <p className="text-rose-500/70 text-sm">{error}</p>
              <button
                onClick={() => router.push("/")}
                className="mt-4 text-sm text-zinc-400 hover:text-zinc-200 flex items-center gap-2"
              >
                <ArrowLeft size={14} />
                Back to Home
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-950/50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center">
              <Shield size={20} className="text-emerald-500" />
            </div>
            <div>
              <h1 className="font-medium text-zinc-100">Admin Panel</h1>
              <p className="text-xs text-zinc-500">User Management</p>
            </div>
          </div>
          <button
            onClick={() => router.push("/")}
            className="text-sm text-zinc-400 hover:text-zinc-200 flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-zinc-900 transition-colors"
          >
            <ArrowLeft size={16} />
            Back to Shell
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
            <div className="flex items-center gap-3 mb-2">
              <Users size={18} className="text-zinc-500" />
              <span className="text-sm text-zinc-400">Total Users</span>
            </div>
            <p className="text-2xl font-medium text-zinc-100">{users.length}</p>
          </div>
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
            <div className="flex items-center gap-3 mb-2">
              <Shield size={18} className="text-emerald-500" />
              <span className="text-sm text-zinc-400">Admins</span>
            </div>
            <p className="text-2xl font-medium text-zinc-100">
              {users.filter((u) => u.is_admin).length}
            </p>
          </div>
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="text-sm text-zinc-400">Active</span>
            </div>
            <p className="text-2xl font-medium text-zinc-100">
              {users.filter((u) => u.is_active).length}
            </p>
          </div>
        </div>

        {/* Users Table */}
        <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-zinc-800">
            <h2 className="font-medium text-zinc-100">User Accounts</h2>
            <p className="text-sm text-zinc-500 mt-1">
              Local accounts with access to the operator shell
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-zinc-900/50">
                  <th className="text-left px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    User
                  </th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Role
                  </th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Created
                  </th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Last Login
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {users.map((user) => (
                  <tr key={user.account_id} className="hover:bg-zinc-900/30">
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-zinc-200">
                          {user.display_name || user.identifier}
                        </span>
                        <span className="text-xs text-zinc-500">{user.identifier}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {user.is_admin ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <Shield size={12} />
                          Admin
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
                          User
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {user.is_active ? (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                          <span className="text-sm text-zinc-400">Active</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-zinc-600" />
                          <span className="text-sm text-zinc-500">Inactive</span>
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-zinc-500">
                        {user.created_at
                          ? new Date(user.created_at).toLocaleDateString()
                          : "—"}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-zinc-500">
                        {user.last_login_at
                          ? new Date(user.last_login_at).toLocaleString()
                          : "Never"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {users.length === 0 && (
              <div className="px-6 py-12 text-center">
                <p className="text-zinc-500 text-sm">No users found</p>
              </div>
            )}
          </div>
        </div>

        {/* Info Box */}
        <div className="mt-8 bg-amber-500/5 border border-amber-500/20 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="text-amber-500 shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-medium text-amber-400">Basic Admin Authorization</h3>
              <p className="text-sm text-amber-500/70 mt-1">
                This panel provides minimal user visibility. The system currently uses a simple
                boolean <code>is_admin</code> flag, not a full RBAC system with roles and
                permissions. Admin users can view all accounts but cannot modify them through this
                interface yet.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
