import { useState, useEffect, useRef, useMemo } from "react";
import { useProtectedRoute } from "@/hooks/use-protected-route";
import { AppLayout } from "@/components/layout";
import { useGetLogs, useClearLogs } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Trash2, Download, Search, Filter } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/lib/auth";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface LogLine {
  id: string | number;
  timestamp: string;
  level: string;
  message: string;
}

export default function Console() {
  useProtectedRoute();
  const { toast } = useToast();
  const { token } = useAuth();

  const [logs, setLogs] = useState<LogLine[]>([]);
  const [search, setSearch] = useState("");
  const [levelFilter, setLevelFilter] = useState<Set<string>>(new Set(["INFO", "WARNING", "ERROR"]));
  const [autoScroll, setAutoScroll] = useState(true);

  const scrollRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const { data: initialLogs } = useGetLogs({ limit: 200 });
  const clearLogs = useClearLogs();

  // Load stored logs on mount
  useEffect(() => {
    if (initialLogs && logs.length === 0) {
      setLogs(initialLogs.map((l: any) => ({ ...l, id: l.id ?? crypto.randomUUID() })));
    }
  }, [initialLogs]);

  // WebSocket — pass JWT via query param (browser WS doesn't support headers)
  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const t = token ?? localStorage.getItem("access_token") ?? "";
      ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/console?token=${encodeURIComponent(t)}`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "log") {
            setLogs((prev) => [
              ...prev,
              { id: crypto.randomUUID(), timestamp: data.timestamp, level: data.level, message: data.message },
            ].slice(-2000));
          } else if (data.type === "clear_logs") {
            // Bot started fresh — wipe the local buffer so stale logs
            // from deleted cogs or previous sessions disappear immediately.
            setLogs([]);
          }
        } catch {/* ignore malformed */ }
      };

      ws.onclose = () => { reconnectTimer = setTimeout(connect, 3000); };
    };

    connect();
    return () => {
      clearTimeout(reconnectTimer);
      if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); }
    };
  }, [token]);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setAutoScroll(Math.abs(scrollHeight - clientHeight - scrollTop) < 10);
  };

  const handleClear = () => {
    clearLogs.mutate(undefined, {
      onSuccess: () => setLogs([]),
      onError: () => toast({ title: "Error", description: "Failed to clear logs", variant: "destructive" }),
    });
  };

  const handleDownload = () => {
    const text = logs.map((l) => `[${l.timestamp}] ${l.level}: ${l.message}`).join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `console-${new Date().toISOString()}.log`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const toggleLevel = (level: string) => {
    setLevelFilter((prev) => {
      const next = new Set(prev);
      next.has(level) ? next.delete(level) : next.add(level);
      return next;
    });
  };

  const filteredLogs = useMemo(() =>
    logs.filter((l) => levelFilter.has(l.level) && (!search || l.message.toLowerCase().includes(search.toLowerCase()))),
    [logs, search, levelFilter],
  );

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-background">

        {/* Toolbar — wraps on mobile */}
        <div className="flex flex-wrap items-center gap-2 p-3 border-b border-border bg-card/50 shrink-0">
          <h1 className="text-lg font-bold tracking-tight mr-2">Console</h1>

          {/* Search — grows on larger screens */}
          <div className="relative flex-1 min-w-[160px]">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Search logs..."
              className="pl-8 bg-background font-mono text-sm h-8"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="gap-1.5 h-8">
                  <Filter size={14} /> Levels
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-40">
                {["INFO", "WARNING", "ERROR"].map((level) => (
                  <DropdownMenuCheckboxItem
                    key={level}
                    checked={levelFilter.has(level)}
                    onCheckedChange={() => toggleLevel(level)}
                  >
                    {level}
                  </DropdownMenuCheckboxItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            <Button variant="outline" size="sm" onClick={handleDownload} className="h-8">
              <Download size={14} className="sm:mr-1.5" />
              <span className="hidden sm:inline">Export</span>
            </Button>

            <Button variant="destructive" size="sm" onClick={handleClear} disabled={clearLogs.isPending} className="h-8">
              <Trash2 size={14} className="sm:mr-1.5" />
              <span className="hidden sm:inline">Clear</span>
            </Button>
          </div>
        </div>

        {/* Log output */}
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto p-3 sm:p-4 font-mono text-xs sm:text-sm bg-[#0a0c10] text-gray-300"
        >
          {filteredLogs.length === 0 ? (
            <div className="text-muted-foreground text-center mt-20">No logs to display</div>
          ) : (
            filteredLogs.map((log) => {
              const date = new Date(log.timestamp);
              const ts = isNaN(date.getTime()) ? log.timestamp
                : date.toLocaleTimeString(undefined, { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })
                  + "." + date.getMilliseconds().toString().padStart(3, "0");

              const colorClass =
                log.level === "WARNING" ? "text-yellow-400"
                : log.level === "ERROR"   ? "text-red-400"
                : "text-blue-400";

              return (
                <div key={log.id} className="flex gap-2 sm:gap-4 py-0.5 hover:bg-white/5 px-2 rounded-sm group">
                  <span className="text-gray-500 shrink-0 select-none">[{ts}]</span>
                  <span className={`shrink-0 w-14 sm:w-16 font-semibold select-none ${colorClass}`}>
                    {log.level}
                  </span>
                  <span className="break-all whitespace-pre-wrap flex-1">{log.message}</span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </AppLayout>
  );
}
