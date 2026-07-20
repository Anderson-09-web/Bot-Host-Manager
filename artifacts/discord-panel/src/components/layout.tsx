import { ReactNode } from "react";
import { Link, useLocation } from "wouter";
import {
  LayoutDashboard,
  FolderOpen,
  Terminal,
  Settings,
  KeyRound,
  LogOut,
  Cpu,
  Bot
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useLogout, useGetBotStatus } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/files", label: "Files", icon: FolderOpen },
  { href: "/console", label: "Console", icon: Terminal },
  { href: "/env-vars", label: "Environment", icon: KeyRound },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppLayout({ children }: { children: ReactNode }) {
  const [location, setLocation] = useLocation();
  const { setToken } = useAuth();
  const logout = useLogout();
  
  const { data: statusData } = useGetBotStatus({
    query: { refetchInterval: 3000 }
  });

  const handleLogout = () => {
    logout.mutate(undefined, {
      onSettled: () => {
        setToken(null);
        setLocation("/login");
      }
    });
  };

  const isOnline = statusData?.status === "online";
  const isStarting = statusData?.status === "starting" || statusData?.status === "restarting";

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground dark selection:bg-primary/30">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border bg-sidebar flex flex-col shrink-0">
        <div className="h-16 flex items-center px-6 border-b border-border shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-primary/20 flex items-center justify-center text-primary">
              <Bot size={20} />
            </div>
            <span className="font-semibold tracking-tight">Control Panel</span>
          </div>
        </div>

        <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = location.startsWith(item.href);
            return (
              <Link key={item.href} href={item.href} className="block">
                <div
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  }`}
                >
                  <item.icon size={18} />
                  <span>{item.label}</span>
                </div>
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-border shrink-0 space-y-4">
          <div className="flex items-center justify-between px-2">
            <span className="text-sm font-medium text-muted-foreground">Bot Status</span>
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${
                  isOnline
                    ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"
                    : isStarting
                    ? "bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.6)] animate-pulse"
                    : "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]"
                }`}
              />
              <span className="text-xs uppercase tracking-wider font-semibold">
                {statusData?.status || "offline"}
              </span>
            </div>
          </div>
          <Button
            variant="ghost"
            className="w-full justify-start text-muted-foreground hover:text-destructive hover:bg-destructive/10"
            onClick={handleLogout}
          >
            <LogOut size={18} className="mr-2" />
            Sign Out
          </Button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden bg-background">
        {children}
      </main>
    </div>
  );
}
