"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Users, Shield, UserCheck, AlertTriangle, RefreshCw } from "lucide-react";
import { listUsers, updateUserRole, getCurrentUser, User } from "@/lib/api";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [msg, setMsg] = useState<string | null>(null);

  const loadUsers = useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await listUsers();
      setUsers(res);
    } catch (err: any) {
      setMsg(`Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const u = getCurrentUser();
    setCurrentUser(u);
    if (u?.role === "ADMIN") {
      loadUsers();
    }
  }, [loadUsers]);

  async function handleRoleChange(userId: number, newRole: "ADMIN" | "TRADER" | "INVITADO") {
    try {
      setMsg(null);
      const updated = await updateUserRole(userId, newRole);
      setMsg(`Rol actualizado para @${updated.username} -> ${updated.role} (Notificación enviada a Telegram).`);
      await loadUsers();
    } catch (err: any) {
      setMsg(`Error al actualizar rol: ${err.message}`);
    }
  }

  if (currentUser && currentUser.role !== "ADMIN") {
    return (
      <div className="glass-panel p-8 rounded-xl text-center space-y-3 max-w-md mx-auto my-12 border border-slate-800">
        <AlertTriangle className="h-10 w-10 text-amber-400 mx-auto" />
        <h2 className="font-mono text-base font-bold text-slate-200">ACCESO RESTRINGIDO</h2>
        <p className="text-xs text-slate-400 font-mono">
          Esta vista está reservada exclusivamente para el rol ADMINISTRADOR.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <a
          href="/"
          className="inline-flex items-center space-x-2 text-xs font-semibold text-rose-400 hover:text-rose-300 transition-colors bg-rose-500/10 px-3 py-1.5 rounded-full border border-rose-500/20"
        >
          <span>← Volver a la App Principal</span>
        </a>
        <span className="text-xs text-slate-400 font-mono">Panel Administrativo</span>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-mono text-xl font-bold text-slate-100 flex items-center space-x-2">
            <Shield className="h-6 w-6 text-emerald-400" />
            <span>CONTROL DE ACCESO & GESTIÓN DE ROLES (RBAC)</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            Administra los permisos de acceso y notifica automáticamente al Telegram de cada usuario.
          </p>
        </div>

        <button
          onClick={loadUsers}
          disabled={isLoading}
          className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono text-xs flex items-center space-x-1.5 self-start sm:self-auto"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          <span>Refrescar</span>
        </button>
      </div>

      {msg && (
        <div className="p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono">
          {msg}
        </div>
      )}

      {/* Tabla de Usuarios */}
      <div className="glass-panel rounded-xl border border-slate-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs font-mono">
            <thead>
              <tr className="bg-slate-900/60 border-b border-slate-800 text-slate-400">
                <th className="py-3 px-4 font-semibold">ID</th>
                <th className="py-3 px-4 font-semibold">Usuario</th>
                <th className="py-3 px-4 font-semibold">Telegram ID</th>
                <th className="py-3 px-4 font-semibold">Estado</th>
                <th className="py-3 px-4 font-semibold">Rol Actual</th>
                <th className="py-3 px-4 font-semibold text-right">Modificar Permisos</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/40">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-900/30 transition-colors">
                  <td className="py-3 px-4 text-slate-400">#{u.id}</td>
                  <td className="py-3 px-4 text-slate-200 font-bold">{u.username}</td>
                  <td className="py-3 px-4 text-slate-300">{u.telegram_id || "--"}</td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${u.is_active ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>
                      {u.is_active ? "ACTIVO" : "SUSPENDIDO"}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${u.role === "ADMIN" ? "bg-purple-500/20 text-purple-300 border border-purple-500/30" : u.role === "TRADER" ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : "bg-slate-800 text-slate-400"}`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, e.target.value as any)}
                      className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono text-xs focus:outline-none focus:border-emerald-500"
                    >
                      <option value="ADMIN">ADMIN</option>
                      <option value="TRADER">TRADER</option>
                      <option value="INVITADO">INVITADO</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
