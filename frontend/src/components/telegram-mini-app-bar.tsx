"use client";

import React, { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Layers, FileSpreadsheet, Users, ShieldAlert, ArrowLeftRight } from "lucide-react";
import { getCurrentUser, User } from "@/lib/api";

export function TelegramMiniAppBar() {
  const [user, setUser] = useState<User | null>(null);
  const pathname = usePathname();

  useEffect(() => {
    setUser(getCurrentUser());
  }, []);

  const navItems = [
    { href: "/", label: "Arbitraje", icon: ArrowLeftRight },
    { href: "/orders", label: "Órdenes", icon: FileSpreadsheet },
    ...(user?.role === "ADMIN" ? [{ href: "/admin", label: "Usuarios", icon: Users }] : []),
    { href: "/login", label: user ? user.role : "Acceso", icon: ShieldAlert },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-[#0e1524]/95 backdrop-blur-md border-t border-[#1e293b] px-3 py-1.5 flex items-center justify-around font-mono text-[11px] shadow-lg">
      {navItems.map((item) => {
        const Icon = item.icon;
        const isActive = pathname === item.href;
        return (
          <a
            key={item.href}
            href={item.href}
            className={`flex flex-col items-center py-1 px-3 rounded-xl transition-all ${
              isActive
                ? "text-emerald-400 bg-emerald-500/10 font-bold"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Icon className={`h-4 w-4 mb-0.5 ${isActive ? "text-emerald-400" : "text-slate-400"}`} />
            <span>{item.label}</span>
          </a>
        );
      })}
    </nav>
  );
}
