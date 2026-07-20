import { useState } from "react";
import { useProtectedRoute } from "@/hooks/use-protected-route";
import { AppLayout } from "@/components/layout";
import {
  useListEnvVars,
  useCreateEnvVar,
  useUpdateEnvVar,
  useDeleteEnvVar,
  getListEnvVarsQueryKey,
} from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Eye, EyeOff, Plus, Trash2, Pencil, Save, X } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Checkbox } from "@/components/ui/checkbox";
import { useQueryClient } from "@tanstack/react-query";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

/* ── Single env-var row (table, desktop) ── */
function EnvRow({
  envVar, onDelete, onUpdate,
}: {
  envVar: any;
  onDelete: (id: number) => void;
  onUpdate: (id: number, data: any) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [showVal, setShowVal] = useState(false);
  const [draft, setDraft] = useState(envVar.value);

  return (
    <TableRow>
      <TableCell className="font-mono font-medium text-sm">{envVar.key}</TableCell>
      <TableCell>
        {editing ? (
          <div className="flex items-center gap-2">
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              type={envVar.is_secret && !showVal ? "password" : "text"}
              className="font-mono h-8 text-sm"
              autoFocus
              onKeyDown={(e) => { if (e.key === "Enter") { onUpdate(envVar.id, { value: draft }); setEditing(false); } }}
            />
            <Button size="icon" variant="ghost" onClick={() => { onUpdate(envVar.id, { value: draft }); setEditing(false); }} className="text-green-500 h-8 w-8">
              <Save size={14} />
            </Button>
            <Button size="icon" variant="ghost" onClick={() => { setDraft(envVar.value); setEditing(false); }} className="text-red-500 h-8 w-8">
              <X size={14} />
            </Button>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-2 group">
            <span className="font-mono text-muted-foreground text-sm truncate max-w-[200px] sm:max-w-xs">
              {envVar.is_secret && !showVal ? "••••••••••••" : envVar.value}
            </span>
            <div className="flex shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
              {envVar.is_secret && (
                <Button size="icon" variant="ghost" onClick={() => setShowVal(!showVal)} className="h-7 w-7">
                  {showVal ? <EyeOff size={13} /> : <Eye size={13} />}
                </Button>
              )}
              <Button size="icon" variant="ghost" onClick={() => setEditing(true)} className="h-7 w-7">
                <Pencil size={13} />
              </Button>
            </div>
          </div>
        )}
      </TableCell>
      <TableCell>
        <span className={`px-2 py-0.5 rounded text-xs font-mono font-semibold ${
          envVar.is_secret ? "bg-red-500/10 text-red-400" : "bg-blue-500/10 text-blue-400"
        }`}>
          {envVar.is_secret ? "SECRET" : "PLAIN"}
        </span>
      </TableCell>
      <TableCell className="text-right">
        <Button size="icon" variant="ghost" onClick={() => onDelete(envVar.id)} className="text-destructive hover:bg-destructive/10 h-8 w-8">
          <Trash2 size={14} />
        </Button>
      </TableCell>
    </TableRow>
  );
}

/* ── Mobile card for one env var ── */
function EnvCard({
  envVar, onDelete, onUpdate,
}: {
  envVar: any;
  onDelete: (id: number) => void;
  onUpdate: (id: number, data: any) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [showVal, setShowVal] = useState(false);
  const [draft, setDraft] = useState(envVar.value);

  return (
    <div className="bg-card/50 border border-border/50 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-mono font-semibold text-sm">{envVar.key}</span>
        <span className={`px-2 py-0.5 rounded text-xs font-mono font-semibold ${
          envVar.is_secret ? "bg-red-500/10 text-red-400" : "bg-blue-500/10 text-blue-400"
        }`}>
          {envVar.is_secret ? "SECRET" : "PLAIN"}
        </span>
      </div>

      {editing ? (
        <div className="flex items-center gap-2">
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            type={envVar.is_secret && !showVal ? "password" : "text"}
            className="font-mono h-8 text-sm flex-1"
            autoFocus
          />
          <Button size="icon" variant="ghost" onClick={() => { onUpdate(envVar.id, { value: draft }); setEditing(false); }} className="text-green-500 h-8 w-8">
            <Save size={14} />
          </Button>
          <Button size="icon" variant="ghost" onClick={() => { setDraft(envVar.value); setEditing(false); }} className="text-red-500 h-8 w-8">
            <X size={14} />
          </Button>
        </div>
      ) : (
        <div className="font-mono text-sm text-muted-foreground break-all">
          {envVar.is_secret && !showVal ? "••••••••••••" : envVar.value}
        </div>
      )}

      <div className="flex items-center gap-2 pt-1 border-t border-border/50">
        {envVar.is_secret && !editing && (
          <Button size="sm" variant="ghost" onClick={() => setShowVal(!showVal)} className="h-7 text-xs gap-1">
            {showVal ? <><EyeOff size={12} /> Hide</> : <><Eye size={12} /> Show</>}
          </Button>
        )}
        {!editing && (
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)} className="h-7 text-xs gap-1">
            <Pencil size={12} /> Edit
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => onDelete(envVar.id)} className="h-7 text-xs gap-1 text-destructive hover:bg-destructive/10 ml-auto">
          <Trash2 size={12} /> Delete
        </Button>
      </div>
    </div>
  );
}

export default function EnvVars() {
  useProtectedRoute();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: envVars, isLoading } = useListEnvVars();
  const createVar = useCreateEnvVar();
  const updateVar = useUpdateEnvVar();
  const deleteVar = useDeleteEnvVar();

  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [newIsSecret, setNewIsSecret] = useState(true);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: getListEnvVarsQueryKey() });

  const handleAdd = () => {
    if (!newKey.trim() || !newValue.trim()) {
      toast({ title: "Error", description: "Key and Value are required", variant: "destructive" });
      return;
    }
    createVar.mutate(
      { data: { key: newKey.trim(), value: newValue.trim(), is_secret: newIsSecret } },
      {
        onSuccess: () => { setNewKey(""); setNewValue(""); setNewIsSecret(true); invalidate(); toast({ title: "Added", description: `${newKey.trim()} saved` }); },
        onError: (e: any) => toast({ title: "Error", description: e.message || "Failed", variant: "destructive" }),
      },
    );
  };

  const handleUpdate = (id: number, data: any) => {
    updateVar.mutate({ id, data }, {
      onSuccess: () => invalidate(),
      onError: (e: any) => toast({ title: "Update Failed", description: e.message, variant: "destructive" }),
    });
  };

  const handleDelete = (id: number) => {
    if (!confirm("Delete this variable?")) return;
    deleteVar.mutate({ id }, {
      onSuccess: () => invalidate(),
    });
  };

  return (
    <AppLayout>
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
        <div className="max-w-5xl mx-auto space-y-6 sm:space-y-8">

          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Environment Variables</h1>
            <p className="text-muted-foreground mt-1 text-sm">Manage secrets and configuration for your bot</p>
          </div>

          {/* Add form */}
          <div className="bg-card/50 border border-border/50 rounded-xl p-4 sm:p-6 backdrop-blur-sm">
            <h2 className="text-base font-semibold mb-4">Add Variable</h2>
            <div className="flex flex-col gap-3">
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1 space-y-1.5">
                  <label className="text-xs font-mono text-muted-foreground uppercase">Key</label>
                  <Input
                    placeholder="DISCORD_TOKEN"
                    value={newKey}
                    onChange={(e) => setNewKey(e.target.value.toUpperCase())}
                    className="font-mono bg-background/50"
                  />
                </div>
                <div className="flex-1 space-y-1.5">
                  <label className="text-xs font-mono text-muted-foreground uppercase">Value</label>
                  <Input
                    placeholder="Paste value..."
                    value={newValue}
                    onChange={(e) => setNewValue(e.target.value)}
                    type={newIsSecret ? "password" : "text"}
                    className="font-mono bg-background/50"
                  />
                </div>
              </div>
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2 px-3 py-2 border border-border/50 rounded-md bg-background/30">
                  <Checkbox id="secret-toggle" checked={newIsSecret} onCheckedChange={(c) => setNewIsSecret(!!c)} />
                  <label htmlFor="secret-toggle" className="text-sm font-medium cursor-pointer">Secret</label>
                </div>
                <Button onClick={handleAdd} disabled={createVar.isPending} className="gap-2">
                  <Plus size={15} /> Add Variable
                </Button>
              </div>
            </div>
          </div>

          {/* Table — desktop */}
          <div className="hidden sm:block bg-card border border-border/50 rounded-xl overflow-hidden">
            <Table>
              <TableHeader className="bg-muted/50">
                <TableRow>
                  <TableHead className="w-[28%] font-mono text-xs">KEY</TableHead>
                  <TableHead className="w-[48%] font-mono text-xs">VALUE</TableHead>
                  <TableHead className="w-[12%] font-mono text-xs">TYPE</TableHead>
                  <TableHead className="w-[12%] text-right font-mono text-xs">ACTIONS</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow><TableCell colSpan={4} className="text-center py-8 text-muted-foreground">Loading...</TableCell></TableRow>
                ) : !envVars?.length ? (
                  <TableRow><TableCell colSpan={4} className="text-center py-8 text-muted-foreground font-mono text-sm">No variables defined.</TableCell></TableRow>
                ) : (
                  envVars.map((v: any) => (
                    <EnvRow key={v.id} envVar={v} onDelete={handleDelete} onUpdate={handleUpdate} />
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {/* Cards — mobile */}
          <div className="sm:hidden space-y-3">
            {isLoading ? (
              <p className="text-center text-muted-foreground py-8">Loading...</p>
            ) : !envVars?.length ? (
              <p className="text-center text-muted-foreground py-8 font-mono text-sm">No variables defined.</p>
            ) : (
              envVars.map((v: any) => (
                <EnvCard key={v.id} envVar={v} onDelete={handleDelete} onUpdate={handleUpdate} />
              ))
            )}
          </div>

        </div>
      </div>
    </AppLayout>
  );
}
