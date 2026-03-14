"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shield, Users, Loader2, AlertTriangle, ArrowLeft, Plus, Key, Power, UserCog } from "lucide-react";

interface User {
  account_id: string;
  identifier: string;
  display_name: string | null;
  is_admin: boolean;
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
}

interface CreateUserForm {
  identifier: string;
  display_name: string;
  password: string;
  is_admin: boolean;
  is_active: boolean;
}

export default function AdminPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [bootstrap, setBootstrap] = useState<any>(null);
  
  // Create user modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState<CreateUserForm>({
    identifier: "",
    display_name: "",
    password: "",
    is_admin: false,
    is_active: true,
  });
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  
  // Reset password modal state
  const [showResetModal, setShowResetModal] = useState(false);
  const [resetUser, setResetUser] = useState<User | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [resetLoading, setResetLoading] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
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

        await loadUsers();
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load admin panel");
        setLoading(false);
      }
    }
    load();
  }, []);

  async function loadUsers() {
    const response = await fetch("/operator-api/admin/users");
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Failed to load users" }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }
    const data = await response.json();
    setUsers(data.users || []);
  }

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    setCreateLoading(true);
    setCreateError(null);

    try {
      const response = await fetch("/operator-api/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(createForm),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Failed to create user" }));
        throw new Error(err.detail || `HTTP ${response.status}`);
      }

      await loadUsers();
      setShowCreateModal(false);
      setCreateForm({
        identifier: "",
        display_name: "",
        password: "",
        is_admin: false,
        is_active: true,
      });
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleToggleActive(user: User) {
    try {
      const response = await fetch(`/operator-api/admin/users/${encodeURIComponent(user.identifier)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !user.is_active }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Failed to update user" }));
        throw new Error(err.detail || `HTTP ${response.status}`);
      }

      await loadUsers();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to update user");
    }
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    if (!resetUser) return;

    setResetLoading(true);
    setResetError(null);

    try {
      const response = await fetch(`/operator-api/admin/users/${encodeURIComponent(resetUser.identifier)}/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_password: resetPassword }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Failed to reset password" }));
        throw new Error(err.detail || `HTTP ${response.status}`);
      }

      setShowResetModal(false);
      setResetUser(null);
      setResetPassword("");
      alert(`Password reset successfully for ${resetUser.identifier}`);
    } catch (err) {
      setResetError(err instanceof Error ? err.message : "Failed to reset password");
    } finally {
      setResetLoading(false);
    }
  }

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

        {/* Action Bar */}
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-medium text-zinc-100">User Accounts</h2>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Plus size={16} />
            Create User
          </button>
        </div>

        {/* Users Table */}
        <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl overflow-hidden">
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
                    Last Login
                  </th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Actions
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
                          <UserCog size={12} />
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
                        {user.last_login_at
                          ? new Date(user.last_login_at).toLocaleString()
                          : "Never"}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => {
                            setResetUser(user);
                            setShowResetModal(true);
                          }}
                          className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-lg transition-colors"
                          title="Reset Password"
                        >
                          <Key size={16} />
                        </button>
                        <button
                          onClick={() => handleToggleActive(user)}
                          className={`p-2 rounded-lg transition-colors ${
                            user.is_active
                              ? "text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
                              : "text-zinc-500 hover:text-zinc-400 hover:bg-zinc-800"
                          }`}
                          title={user.is_active ? "Deactivate" : "Activate"}
                        >
                          <Power size={16} />
                        </button>
                      </div>
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
                This panel provides user management with a simple boolean <code>is_admin</code> flag,
                not a full RBAC system. Admin users can create accounts, toggle active status, and
                reset passwords. Passwords must be at least 12 characters.
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl max-w-md w-full p-6">
            <h3 className="text-lg font-medium text-zinc-100 mb-4">Create New User</h3>
            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="block text-sm text-zinc-400 mb-1">Email / Username</label>
                <input
                  type="text"
                  value={createForm.identifier}
                  onChange={(e) => setCreateForm({ ...createForm, identifier: e.target.value })}
                  className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-100 focus:outline-none focus:border-zinc-700"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-zinc-400 mb-1">Display Name (optional)</label>
                <input
                  type="text"
                  value={createForm.display_name}
                  onChange={(e) => setCreateForm({ ...createForm, display_name: e.target.value })}
                  className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-100 focus:outline-none focus:border-zinc-700"
                />
              </div>
              <div>
                <label className="block text-sm text-zinc-400 mb-1">
                  Password <span className="text-zinc-600">(min 12 characters)</span>
                </label>
                <input
                  type="password"
                  value={createForm.password}
                  onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                  className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-100 focus:outline-none focus:border-zinc-700"
                  minLength={12}
                  required
                />
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={createForm.is_admin}
                    onChange={(e) => setCreateForm({ ...createForm, is_admin: e.target.checked })}
                    className="rounded border-zinc-700 bg-zinc-800"
                  />
                  <span className="text-sm text-zinc-400">Admin</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={createForm.is_active}
                    onChange={(e) => setCreateForm({ ...createForm, is_active: e.target.checked })}
                    className="rounded border-zinc-700 bg-zinc-800"
                  />
                  <span className="text-sm text-zinc-400">Active</span>
                </label>
              </div>
              {createError && (
                <div className="text-sm text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg p-3">
                  {createError}
                </div>
              )}
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createLoading}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
                >
                  {createLoading && <Loader2 size={14} className="animate-spin" />}
                  Create User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {showResetModal && resetUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl max-w-md w-full p-6">
            <h3 className="text-lg font-medium text-zinc-100 mb-2">Reset Password</h3>
            <p className="text-sm text-zinc-500 mb-4">
              Set a new password for <span className="text-zinc-300">{resetUser.identifier}</span>
            </p>
            <form onSubmit={handleResetPassword} className="space-y-4">
              <div>
                <label className="block text-sm text-zinc-400 mb-1">
                  New Password <span className="text-zinc-600">(min 12 characters)</span>
                </label>
                <input
                  type="password"
                  value={resetPassword}
                  onChange={(e) => setResetPassword(e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-100 focus:outline-none focus:border-zinc-700"
                  minLength={12}
                  required
                  autoFocus
                />
              </div>
              {resetError && (
                <div className="text-sm text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg p-3">
                  {resetError}
                </div>
              )}
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowResetModal(false);
                    setResetUser(null);
                    setResetPassword("");
                  }}
                  className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={resetLoading}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
                >
                  {resetLoading && <Loader2 size={14} className="animate-spin" />}
                  Reset Password
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
