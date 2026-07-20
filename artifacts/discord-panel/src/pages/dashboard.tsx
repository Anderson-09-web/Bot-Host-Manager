import { useProtectedRoute } from "@/hooks/use-protected-route";
import { AppLayout } from "@/components/layout";
import { useGetMetrics, useGetBotStatus, useStartBot, useStopBot, useRestartBot, useKillBot, getGetBotStatusQueryKey, getGetMetricsQueryKey } from "@workspace/api-client-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Play, Square, RotateCcw, Skull, Activity, Cpu, HardDrive, Clock, Terminal, FolderGit2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Progress } from "@/components/ui/progress";

function formatUptime(seconds?: number | null) {
  if (!seconds) return "0s";
  const d = Math.floor(seconds / (3600 * 24));
  const h = Math.floor((seconds % (3600 * 24)) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${Math.floor(seconds % 60)}s`;
}

function MetricCard({
  title, icon: Icon, value, subValue, progress,
}: {
  title: string; icon: any; value: string | number; subValue?: string; progress?: number;
}) {
  return (
    <Card className="bg-card/50 border-border/50 backdrop-blur-sm">
      <CardContent className="p-4 sm:p-6">
        <div className="flex items-center gap-2 text-muted-foreground mb-3">
          <Icon size={15} />
          <span className="font-mono text-xs tracking-wider uppercase">{title}</span>
        </div>
        <div className="space-y-2">
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-mono font-medium">{value}</span>
            {subValue && <span className="text-sm text-muted-foreground font-mono">{subValue}</span>}
          </div>
          {progress !== undefined && (
            <Progress value={progress} className="h-1 bg-muted/50" />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  useProtectedRoute();
  const { toast } = useToast();

  const { data: metrics } = useGetMetrics({ query: { queryKey: getGetMetricsQueryKey(), refetchInterval: 3000 } });
  const { data: status  } = useGetBotStatus({ query: { queryKey: getGetBotStatusQueryKey(), refetchInterval: 3000 } });

  const startBot   = useStartBot();
  const stopBot    = useStopBot();
  const restartBot = useRestartBot();
  const killBot    = useKillBot();

  const handleAction = (action: any, name: string) => {
    action.mutate(undefined, {
      onSuccess: () => toast({ title: "Command Sent", description: `Executed: ${name}` }),
      onError:   (err: any) => toast({ title: "Failed", description: err.message || "Unknown error", variant: "destructive" }),
    });
  };

  const isOffline  = !status?.status || status.status === "offline";
  const isRunning  = status?.status === "online" || status?.status === "starting" || status?.status === "restarting";

  return (
    <AppLayout>
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 space-y-6 sm:space-y-8">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">System Telemetry</h1>
            <p className="text-muted-foreground mt-1 text-sm">Real-time metrics and instance control</p>
          </div>

          {/* Controls — wraps naturally on small screens */}
          <div className="flex flex-wrap items-center gap-2 bg-card/50 border border-border/50 p-2 rounded-lg backdrop-blur-sm">
            <Button
              variant="ghost" size="sm"
              onClick={() => handleAction(startBot, "START")}
              disabled={!isOffline || startBot.isPending}
              className="text-green-500 hover:text-green-400 hover:bg-green-500/10"
            >
              <Play size={15} className="mr-1.5" /> Start
            </Button>
            <div className="w-px h-5 bg-border" />
            <Button
              variant="ghost" size="sm"
              onClick={() => handleAction(restartBot, "RESTART")}
              disabled={isOffline || restartBot.isPending}
              className="text-blue-500 hover:text-blue-400 hover:bg-blue-500/10"
            >
              <RotateCcw size={15} className="mr-1.5" /> Restart
            </Button>
            <div className="w-px h-5 bg-border" />
            <Button
              variant="ghost" size="sm"
              onClick={() => handleAction(stopBot, "STOP")}
              disabled={isOffline || stopBot.isPending}
              className="text-yellow-500 hover:text-yellow-400 hover:bg-yellow-500/10"
            >
              <Square size={15} className="mr-1.5" /> Stop
            </Button>
            <div className="w-px h-5 bg-border" />
            <Button
              variant="ghost" size="sm"
              onClick={() => handleAction(killBot, "KILL")}
              disabled={isOffline || killBot.isPending}
              className="text-red-500 hover:text-red-400 hover:bg-red-500/10"
            >
              <Skull size={15} className="mr-1.5" /> Kill
            </Button>
          </div>
        </div>

        {/* System Metrics */}
        <div>
          <h2 className="text-sm font-mono uppercase tracking-widest text-muted-foreground mb-3">System</h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <MetricCard title="CPU" icon={Cpu}
              value={`${metrics?.cpu_percent?.toFixed(1) ?? 0}%`}
              progress={metrics?.cpu_percent ?? 0} />
            <MetricCard title="Memory" icon={Activity}
              value={`${((metrics?.ram_used_mb ?? 0) / 1024).toFixed(1)}GB`}
              subValue={`/ ${((metrics?.ram_total_mb ?? 0) / 1024).toFixed(1)}GB`}
              progress={metrics?.ram_percent ?? 0} />
            <MetricCard title="Storage" icon={HardDrive}
              value={`${metrics?.disk_used_gb?.toFixed(1) ?? 0}GB`}
              subValue={`/ ${metrics?.disk_total_gb?.toFixed(1) ?? 0}GB`}
              progress={metrics?.disk_percent ?? 0} />
            <MetricCard title="Uptime" icon={Clock}
              value={formatUptime(metrics?.uptime_seconds)} />
          </div>
        </div>

        {/* Bot Metrics */}
        <div>
          <h2 className="text-sm font-mono uppercase tracking-widest text-muted-foreground mb-3">Bot Process</h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <MetricCard title="Bot CPU" icon={Cpu}
              value={`${metrics?.bot_cpu_percent?.toFixed(1) ?? 0}%`} />
            <MetricCard title="Bot Memory" icon={Activity}
              value={`${metrics?.bot_memory_mb?.toFixed(1) ?? 0}MB`} />
            <MetricCard title="Process ID" icon={Terminal}
              value={metrics?.bot_pid ?? "---"}
              subValue={metrics?.python_version ? `py${metrics.python_version}` : undefined} />
            <MetricCard title="Files" icon={FolderGit2}
              value={metrics?.file_count ?? 0}
              subValue="in workspace" />
          </div>
        </div>

      </div>
    </AppLayout>
  );
}
