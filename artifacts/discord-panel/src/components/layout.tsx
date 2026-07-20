import { ReactNode, useState } from "react";
import { Link, useLocation } from "wouter";
import {
  LayoutDashboard,
  FolderOpen,
  Terminal,
  Settings,
  KeyRound,
  LogOut,
  Bot,
  Menu,
  X,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useLogout, useGetBotStatus, getGetBotStatusQueryKey } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/files",     label: "Files",      icon: FolderOpen },
  { href: "/console",   label: "Console",    icon: Terminal },
  { href: "/env-vars",  label: "Environment",icon: KeyRound },
  { href: "/settings",  label: "Settings",   icon: Settings },
];

function StatusDot({ status }: { status?: string }) {
  const isOnline   = status === "online";
  const isStarting = status === "starting" || status === "restarting";
  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full shrink-0 ${
        isOnline   ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"
        : isStarting ? "bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.6)] animate-pulse"
        : "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]"
      }`} />
      <span className="text-xs uppercase tracking-wider font-semibold font-mono">
        {status || "offline"}
      </span>
    </div>
  );
}

function SidebarContent({
  location,
  statusData,
  onNav,
  onLogout,
  logoutPending,
}: {
  location: string;
  statusData: any;
  onNav: () => void;
  onLogout: () => void;
  logoutPending: boolean;
}) {
  return (
    <>
      {/* Logo */}
      <div className="h-16 flex items-center px-6 border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-primary/20 flex items-center justify-center text-primary">
            <Bot size={20} />
          </div>
          <span className="font-semibold tracking-tight">Control Panel</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = location.startsWith(item.href);
          return (
            <Link key={item.href} href={item.href} onClick={onNav} className="block">
              <div className={`flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors ${
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}>
                <item.icon size={18} />
                <span>{item.label}</span>
              </div>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-border shrink-0 space-y-4">
        <div className="flex items-center justify-between px-2">
          <span className="text-sm font-medium text-muted-foreground">Bot Status</span>
          <StatusDot status={statusData?.status} />
        </div>
        <Button
          variant="ghost"
          className="w-full justify-start text-muted-foreground hover:text-destructive hover:bg-destructive/10"
          onClick={onLogout}
          disabled={logoutPending}
        >
          <LogOut size={18} className="mr-2" />
          Sign Out
        </Button>
      </div>
    </>
  );
}

export function AppLayout({ children }: { children: ReactNode }) {
  const [location, setLocation] = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { setToken } = useAuth();
  const logout = useLogout();

  const { data: statusData } = useGetBotStatus({ query: { queryKey: getGetBotStatusQueryKey(), refetchInterval: 3000 } });

  const handleLogout = () => {
    logout.mutate(undefined, {
      onSettled: () => { setToken(null); setLocation("/login"); },
    });
  };

  const closeNav = () => setMobileOpen(false);

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground dark selection:bg-primary/30">

      {/* ── Mobile overlay sidebar ───────────────────────────────── */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={closeNav}
          />
          {/* Drawer */}
          <aside className="relative z-10 w-72 h-full bg-sidebar border-r border-border flex flex-col">
            {/* Close button */}
            <button
              onClick={closeNav}
              className="absolute top-4 right-4 p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <X size={18} />
            </button>
            <SidebarContent
              location={location}
              statusData={statusData}
              onNav={closeNav}
              onLogout={handleLogout}
              logoutPending={logout.isPending}
            />
          </aside>
        </div>
      )}

      {/* ── Desktop sidebar (hidden on mobile) ──────────────────── */}
      <aside className="hidden md:flex w-64 border-r border-border bg-sidebar flex-col shrink-0">
        <SidebarContent
          location={location}
          statusData={statusData}
          onNav={() => {}}
          onLogout={handleLogout}
          logoutPending={logout.isPending}
        />
      </aside>

      {/* ── Main area ────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-background">
        {/* Mobile top bar */}
        <header className="md:hidden flex items-center justify-between h-14 px-4 border-b border-border bg-sidebar shrink-0">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <Menu size={20} />
          </button>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Bot size={18} className="text-primary" />
            Control Panel
          </div>
          <StatusDot status={statusData?.status} />
        </header>

        {/* Page content */}
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}
