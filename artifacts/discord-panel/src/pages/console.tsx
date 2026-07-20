import { useState, useEffect, useRef, useMemo } from "react";
import { useProtectedRoute } from "@/hooks/use-protected-route";
import { AppLayout } from "@/components/layout";
import { useGetLogs, useClearLogs } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Trash2, Download, Search, Filter } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
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
  
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [search, setSearch] = useState("");
  const [levelFilter, setLevelFilter] = useState<Set<string>>(new Set(["INFO", "WARNING", "ERROR"]));
  const [autoScroll, setAutoScroll] = useState(true);
  
  const scrollRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const { data: initialLogs } = useGetLogs({ limit: 100 });
  const clearLogs = useClearLogs();

  // Load initial logs
  useEffect(() => {
    if (initialLogs && logs.length === 0) {
      setLogs(initialLogs.map(l => ({ ...l, id: l.id || crypto.randomUUID() })));
    }
  }, [initialLogs]);

  // Setup WebSocket
  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: any;
    
    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/api/ws/console`;
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "log") {
            setLogs(prev => [...prev, {
              id: crypto.randomUUID(),
              timestamp: data.timestamp,
              level: data.level,
              message: data.message
            }].slice(-1000)); // Keep last 1000 logs
          }
        } catch (e) {
          console.error("Failed to parse WS message", e);
        }
      };

      ws.onclose = () => {
        reconnectTimer = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, []);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = Math.abs(scrollHeight - clientHeight - scrollTop) < 10;
    setAutoScroll(isAtBottom);
  };

  const handleClear = () => {
    clearLogs.mutate(undefined, {
      onSuccess: () => setLogs([]),
      onError: () => toast({ title: "Error", description: "Failed to clear logs", variant: "destructive" })
    });
  };

  const handleDownload = () => {
    const text = logs.map(l => `[${l.timestamp}] ${l.level}: ${l.message}`).join("\n");
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `console-${new Date().toISOString()}.log`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const toggleLevel = (level: string) => {
    setLevelFilter(prev => {
      const next = new Set(prev);
      if (next.has(level)) next.delete(level);
      else next.add(level);
      return next;
    });
  };

  const filteredLogs = useMemo(() => {
    return logs.filter(l => {
      if (!levelFilter.has(l.level)) return false;
      if (search && !l.message.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [logs, search, levelFilter]);

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-background">
        <div className="flex items-center justify-between p-4 border-b border-border bg-card/50 shrink-0">
          <div className="flex items-center gap-4 flex-1">
            <h1 className="text-xl font-bold tracking-tight">Console</h1>
            <div className="relative max-w-sm w-full">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search logs..."
                className="pl-9 bg-background font-mono text-sm"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2">
                  <Filter size={16} /> Levels
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-40">
                {["INFO", "WARNING", "ERROR"].map(level => (
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

            <Button variant="outline" size="sm" onClick={handleDownload}>
              <Download size={16} className="mr-2" /> Export
            </Button>
            
            <Button variant="destructive" size="sm" onClick={handleClear} disabled={clearLogs.isPending}>
              <Trash2 size={16} className="mr-2" /> Clear
            </Button>
          </div>
        </div>

        <div 
          ref={scrollRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto p-4 font-mono text-sm bg-[#0a0c10] text-gray-300"
        >
          {filteredLogs.length === 0 ? (
            <div className="text-muted-foreground text-center mt-20">No logs to display</div>
          ) : (
            filteredLogs.map(log => {
              const date = new Date(log.timestamp);
              const timeString = isNaN(date.getTime()) ? log.timestamp : date.toLocaleTimeString(undefined, {
                hour12: false,
                hour: '2-digit',
                minute:'2-digit',
                second:'2-digit',
              }) + '.' + date.getMilliseconds().toString().padStart(3, '0');

              let colorClass = "text-blue-400";
              if (log.level === "WARNING") colorClass = "text-yellow-400";
              if (log.level === "ERROR") colorClass = "text-red-400";

              return (
                <div key={log.id} className="flex gap-4 py-0.5 hover:bg-white/5 transition-colors px-2 rounded-sm group">
                  <span className="text-gray-500 shrink-0 select-none">[{timeString}]</span>
                  <span className={`shrink-0 w-16 font-semibold select-none ${colorClass}`}>
                    {log.level.padEnd(7)}
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
