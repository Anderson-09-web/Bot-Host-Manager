import { useState, useEffect } from "react";
import { useProtectedRoute } from "@/hooks/use-protected-route";
import { AppLayout } from "@/components/layout";
import { useGetConfig, useUpdateConfig, useGetAuditLogs } from "@workspace/api-client-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Settings2, Save, Activity } from "lucide-react";

export default function Settings() {
  useProtectedRoute();
  const { toast } = useToast();

  const { data: config } = useGetConfig();
  const { data: auditLogs } = useGetAuditLogs({ limit: 50 });
  const updateConfig = useUpdateConfig();

  const [botName,       setBotName]       = useState("");
  const [mainFile,      setMainFile]      = useState("");
  const [pythonVersion, setPythonVersion] = useState("");
  const [autoRestart,   setAutoRestart]   = useState(false);
  const [maxLogLines,   setMaxLogLines]   = useState(1000);

  useEffect(() => {
    if (config) {
      setBotName(config.bot_name ?? "");
      setMainFile(config.main_file ?? "");
      setPythonVersion(config.python_version ?? "");
      setAutoRestart(config.auto_restart ?? false);
      setMaxLogLines(config.max_log_lines ?? 1000);
    }
  }, [config]);

  const handleSave = () => {
    updateConfig.mutate({
      data: {
        bot_name: botName,
        main_file: mainFile,
        python_version: pythonVersion,
        auto_restart: autoRestart,
        max_log_lines: Number(maxLogLines),
      },
    }, {
      onSuccess: () => toast({ title: "Saved", description: "Configuration updated." }),
      onError: (e: any) => toast({ title: "Save Failed", description: e.message, variant: "destructive" }),
    });
  };

  return (
    <AppLayout>
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
        <div className="max-w-5xl mx-auto space-y-6 sm:space-y-8">

          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Settings</h1>
            <p className="text-muted-foreground mt-1 text-sm">Configure bot behavior and view system audit logs</p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 sm:gap-8">

            {/* Configuration form */}
            <Card className="bg-card/50 border-border/50 backdrop-blur-sm">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Settings2 size={18} className="text-primary" />
                  <CardTitle className="text-lg">Instance Configuration</CardTitle>
                </div>
                <CardDescription>Core parameters for your Python environment</CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">

                <div className="space-y-1.5">
                  <label className="text-xs font-mono font-medium text-muted-foreground uppercase">Bot Name</label>
                  <Input value={botName} onChange={(e) => setBotName(e.target.value)} className="font-mono bg-background/50" />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-mono font-medium text-muted-foreground uppercase">Main Entry File</label>
                  <Input value={mainFile} onChange={(e) => setMainFile(e.target.value)} placeholder="main.py" className="font-mono bg-background/50" />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-mono font-medium text-muted-foreground uppercase">Python Version</label>
                  <Input value={pythonVersion} onChange={(e) => setPythonVersion(e.target.value)} placeholder="3.11" className="font-mono bg-background/50" />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-mono font-medium text-muted-foreground uppercase">Max Log Lines</label>
                  <Input type="number" value={maxLogLines} onChange={(e) => setMaxLogLines(Number(e.target.value))} className="font-mono bg-background/50" />
                </div>

                <div className="flex items-center justify-between p-4 border border-border/50 rounded-lg bg-background/30">
                  <div>
                    <p className="text-sm font-medium">Auto Restart</p>
                    <p className="text-xs text-muted-foreground mt-0.5">Restart automatically on crash</p>
                  </div>
                  <Switch checked={autoRestart} onCheckedChange={setAutoRestart} />
                </div>

                <Button onClick={handleSave} disabled={updateConfig.isPending} className="w-full gap-2">
                  <Save size={15} />
                  {updateConfig.isPending ? "Saving..." : "Save Configuration"}
                </Button>

              </CardContent>
            </Card>

            {/* Audit log */}
            <Card className="bg-card/50 border-border/50 backdrop-blur-sm flex flex-col lg:max-h-[600px]">
              <CardHeader className="shrink-0">
                <div className="flex items-center gap-2">
                  <Activity size={18} className="text-primary" />
                  <CardTitle className="text-lg">Audit Log</CardTitle>
                </div>
                <CardDescription>Recent actions on this instance</CardDescription>
              </CardHeader>
              <CardContent className="flex-1 overflow-auto p-0">
                <Table>
                  <TableHeader className="bg-muted/50 sticky top-0 backdrop-blur-sm">
                    <TableRow>
                      <TableHead className="font-mono text-xs w-[100px]">TIME</TableHead>
                      <TableHead className="font-mono text-xs">ACTION</TableHead>
                      <TableHead className="font-mono text-xs w-[80px]">USER</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {auditLogs?.map((log: any) => {
                      const d = new Date(log.created_at);
                      return (
                        <TableRow key={log.id}>
                          <TableCell className="font-mono text-xs text-muted-foreground whitespace-nowrap">
                            {d.toLocaleDateString()} {d.toLocaleTimeString()}
                          </TableCell>
                          <TableCell className="text-sm">
                            <div className="font-medium">{log.action}</div>
                            {log.details && <div className="text-xs text-muted-foreground mt-0.5">{log.details}</div>}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">{log.username ?? "System"}</TableCell>
                        </TableRow>
                      );
                    })}
                    {!auditLogs?.length && (
                      <TableRow>
                        <TableCell colSpan={3} className="text-center py-8 text-muted-foreground text-sm">
                          No audit logs yet.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

          </div>
        </div>
      </div>
    </AppLayout>
  );
}
