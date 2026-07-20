import { useState, useRef, useEffect } from "react";
import { useProtectedRoute } from "@/hooks/use-protected-route";
import { AppLayout } from "@/components/layout";
import {
  useListFiles, useDeleteFile, useGetFileContent, useUpdateFileContent,
  useCreateFile, useRenameFile, useMoveFile, useCopyFile,
  getListFilesQueryKey, getGetFileContentQueryKey,
} from "@workspace/api-client-react";
import { useAuth } from "@/lib/auth";
import { useQueryClient } from "@tanstack/react-query";
import {
  Folder, File as FileIcon, FileCode2, FileJson, FileText, Image as ImageIcon,
  Upload, Plus, RefreshCw, Download, Trash2, Edit2, Pencil, Copy,
  MoveRight, ChevronRight, FolderPlus, ArrowLeft,
} from "lucide-react";
import {
  ContextMenu, ContextMenuContent, ContextMenuItem,
  ContextMenuSeparator, ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import CodeMirror from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";
import { json } from "@codemirror/lang-json";
import { oneDark } from "@codemirror/theme-one-dark";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";

const getFileIcon = (filename: string, isFolder: boolean) => {
  if (isFolder) return <Folder size={17} className="text-blue-400 fill-blue-400/20 shrink-0" />;
  if (filename.endsWith(".py"))   return <FileCode2 size={17} className="text-yellow-400 shrink-0" />;
  if (filename.endsWith(".json")) return <FileJson  size={17} className="text-green-400 shrink-0" />;
  if (/\.(png|jpe?g|gif|ico|webp)$/i.test(filename)) return <ImageIcon size={17} className="text-purple-400 shrink-0" />;
  return <FileText size={17} className="text-muted-foreground shrink-0" />;
};

type DialogState =
  | { type: "none" }
  | { type: "new_file" | "new_folder"; basePath: string }
  | { type: "rename"; path: string; currentName: string }
  | { type: "move" | "copy"; path: string }
  | { type: "delete"; path: string };

export default function Files() {
  useProtectedRoute();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { token } = useAuth();

  const [currentPath,     setCurrentPath]     = useState("/");
  const [selectedFile,    setSelectedFile]     = useState<string | null>(null);
  const [editorContent,   setEditorContent]   = useState("");
  const [dialogState,     setDialogState]     = useState<DialogState>({ type: "none" });
  const [dialogInput,     setDialogInput]     = useState("");
  // Mobile: which panel to show ("tree" | "editor")
  const [mobileView,      setMobileView]      = useState<"tree" | "editor">("tree");

  const fileInputRef = useRef<HTMLInputElement>(null);
  const initializedRef = useRef<string | null>(null);
  const lastSavedRef   = useRef("");
  const mutateFnRef    = useRef<any>(null);

  const { data: fileList, isLoading, refetch } = useListFiles(
    { path: currentPath === "/" ? "" : currentPath },
    { query: { queryKey: getListFilesQueryKey({ path: currentPath === "/" ? "" : currentPath }) } },
  );

  const { data: fileContent, isFetching: isContentFetching } = useGetFileContent(
    { path: selectedFile ?? "" },
    { query: { enabled: !!selectedFile, queryKey: getGetFileContentQueryKey({ path: selectedFile ?? "" }) } },
  );

  const updateContent = useUpdateFileContent();
  const deleteFile    = useDeleteFile();
  const createFile    = useCreateFile();
  const renameFile    = useRenameFile();
  const moveFile      = useMoveFile();
  const copyFile      = useCopyFile();

  mutateFnRef.current = updateContent.mutate;

  // Sync editor when file changes
  useEffect(() => {
    if (fileContent && selectedFile && initializedRef.current !== selectedFile) {
      initializedRef.current = selectedFile;
      setEditorContent(fileContent.content ?? "");
      lastSavedRef.current = fileContent.content ?? "";
    }
  }, [fileContent, selectedFile]);

  // Auto-save (1 s debounce)
  useEffect(() => {
    if (!selectedFile || initializedRef.current !== selectedFile) return;
    const timer = setTimeout(() => {
      if (editorContent !== lastSavedRef.current) {
        mutateFnRef.current(
          { data: { path: selectedFile, content: editorContent } },
          {
            onSuccess: () => {
              lastSavedRef.current = editorContent;
              queryClient.setQueryData(getGetFileContentQueryKey({ path: selectedFile }), (old: any) =>
                old ? { ...old, content: editorContent } : old,
              );
            },
            onError: (e: any) => toast({ title: "Save Failed", description: e.message, variant: "destructive" }),
          },
        );
      }
    }, 1000);
    return () => clearTimeout(timer);
  }, [editorContent, selectedFile, queryClient]);

  /* ── Actions ── */
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append("file", file);
    formData.append("path", currentPath === "/" ? "" : currentPath);
    try {
      const res = await fetch("/api/files/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (!res.ok) throw new Error("Upload failed");
      toast({ title: "Uploaded", description: file.name });
      refetch();
    } catch (err: any) {
      toast({ title: "Upload Failed", description: err.message, variant: "destructive" });
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDownload = async (path: string) => {
    try {
      const res = await fetch(`/api/files/download?path=${encodeURIComponent(path)}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Download failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = path.split("/").pop() ?? "download";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      toast({ title: "Download Failed", description: err.message, variant: "destructive" });
    }
  };

  const closeDialog = () => { setDialogState({ type: "none" }); setDialogInput(""); };

  const submitDialog = () => {
    if (dialogState.type === "none") return;
    const base = currentPath === "/" ? "" : currentPath;

    if (dialogState.type === "new_file") {
      createFile.mutate({ data: { path: base ? `${base}/${dialogInput}` : dialogInput, type: "file", content: "" } }, { onSuccess: () => { refetch(); closeDialog(); } });
    } else if (dialogState.type === "new_folder") {
      createFile.mutate({ data: { path: base ? `${base}/${dialogInput}` : dialogInput, type: "folder" } }, { onSuccess: () => { refetch(); closeDialog(); } });
    } else if (dialogState.type === "rename") {
      renameFile.mutate({ data: { path: dialogState.path, new_name: dialogInput } }, {
        onSuccess: () => { if (selectedFile === dialogState.path) setSelectedFile(null); refetch(); closeDialog(); },
      });
    } else if (dialogState.type === "move") {
      moveFile.mutate({ data: { source: dialogState.path, destination: dialogInput } }, { onSuccess: () => { refetch(); closeDialog(); } });
    } else if (dialogState.type === "copy") {
      copyFile.mutate({ data: { source: dialogState.path, destination: dialogInput } }, { onSuccess: () => { refetch(); closeDialog(); } });
    } else if (dialogState.type === "delete") {
      deleteFile.mutate({ params: { path: dialogState.path } }, {
        onSuccess: () => {
          if (selectedFile === dialogState.path) {
            setSelectedFile(null);
            // Reset so the same path can be re-opened cleanly later
            initializedRef.current = null;
            setEditorContent("");
          }
          refetch();
          closeDialog();
        },
      });
    }
  };

  const navigateUp = () => {
    if (currentPath === "/") return;
    const parts = currentPath.split("/");
    parts.pop();
    setCurrentPath(parts.join("/") || "/");
  };

  const breadcrumbs = currentPath.split("/").filter(Boolean);

  const getExtensions = () => {
    if (!selectedFile) return [];
    if (selectedFile.endsWith(".py"))   return [python()];
    if (selectedFile.endsWith(".json")) return [json()];
    return [];
  };

  const openFile = (path: string) => {
    setSelectedFile(path);
    setMobileView("editor");
  };

  /* ── File tree panel (shared between mobile and desktop) ── */
  const FileTree = (
    <div className="flex flex-col h-full bg-sidebar">
      {/* Toolbar */}
      <div className="flex items-center gap-1.5 p-2 border-b border-border flex-wrap shrink-0">
        <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => setDialogState({ type: "new_file", basePath: currentPath })}>
          <FileIcon size={12} className="mr-1" /> File
        </Button>
        <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => setDialogState({ type: "new_folder", basePath: currentPath })}>
          <FolderPlus size={12} className="mr-1" /> Folder
        </Button>
        <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => fileInputRef.current?.click()}>
          <Upload size={12} className="mr-1" /> Upload
          <input type="file" className="hidden" ref={fileInputRef} onChange={handleUpload} />
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7 ml-auto" onClick={() => refetch()}>
          <RefreshCw size={12} className={isLoading ? "animate-spin" : ""} />
        </Button>
      </div>

      {/* Breadcrumb */}
      <div className="flex items-center text-xs font-mono text-muted-foreground gap-1 px-3 py-2 border-b border-border/50 overflow-x-auto shrink-0">
        <span className="cursor-pointer hover:text-primary transition-colors shrink-0" onClick={() => setCurrentPath("/")}>root</span>
        {breadcrumbs.map((part, i) => {
          const path = "/" + breadcrumbs.slice(0, i + 1).join("/");
          return (
            <span key={path} className="flex items-center gap-1 shrink-0">
              <ChevronRight size={12} />
              <span className="cursor-pointer hover:text-primary transition-colors" onClick={() => setCurrentPath(path)}>{part}</span>
            </span>
          );
        })}
      </div>

      {/* Items */}
      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {currentPath !== "/" && (
          <div className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted cursor-pointer text-xs font-mono text-muted-foreground" onClick={navigateUp}>
            <Folder size={16} className="text-blue-400/50" /><span>..</span>
          </div>
        )}
        {fileList?.items.map((item: any) => (
          <ContextMenu key={item.path}>
            <ContextMenuTrigger>
              <div
                className={`flex items-center justify-between px-2 py-1.5 rounded cursor-pointer text-xs font-mono group transition-colors ${
                  selectedFile === item.path ? "bg-primary/20 text-primary" : "hover:bg-muted"
                }`}
                onClick={() => item.type === "folder" ? setCurrentPath(item.path) : openFile(item.path)}
              >
                <div className="flex items-center gap-2 overflow-hidden">
                  {getFileIcon(item.name, item.type === "folder")}
                  <span className="truncate">{item.name}</span>
                </div>
                {item.type === "file" && item.size > 0 && (
                  <span className="text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                    {(item.size / 1024).toFixed(1)}KB
                  </span>
                )}
              </div>
            </ContextMenuTrigger>
            <ContextMenuContent className="w-48 font-mono text-sm">
              {item.type === "file" && (
                <ContextMenuItem onClick={() => openFile(item.path)}><Edit2 size={13} className="mr-2" /> Edit</ContextMenuItem>
              )}
              <ContextMenuItem onClick={() => setDialogState({ type: "rename", path: item.path, currentName: item.name })}><Pencil size={13} className="mr-2" /> Rename</ContextMenuItem>
              <ContextMenuItem onClick={() => setDialogState({ type: "move", path: item.path })}><MoveRight size={13} className="mr-2" /> Move</ContextMenuItem>
              <ContextMenuItem onClick={() => setDialogState({ type: "copy", path: item.path })}><Copy size={13} className="mr-2" /> Copy</ContextMenuItem>
              {item.type === "file" && (
                <ContextMenuItem onClick={() => handleDownload(item.path)}><Download size={13} className="mr-2" /> Download</ContextMenuItem>
              )}
              <ContextMenuSeparator />
              <ContextMenuItem className="text-destructive focus:bg-destructive focus:text-destructive-foreground" onClick={() => setDialogState({ type: "delete", path: item.path })}>
                <Trash2 size={13} className="mr-2" /> Delete
              </ContextMenuItem>
            </ContextMenuContent>
          </ContextMenu>
        ))}
        {fileList?.items.length === 0 && (
          <div className="text-center text-muted-foreground text-xs py-8 font-mono">Empty directory</div>
        )}
      </div>
    </div>
  );

  /* ── Editor panel ── */
  const Editor = (
    <div className="flex flex-col h-full bg-[#282c34]">
      {selectedFile ? (
        <>
          <div className="flex items-center justify-between px-3 py-2 bg-sidebar border-b border-border shrink-0">
            {/* Back button on mobile */}
            <button
              className="md:hidden mr-2 p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted"
              onClick={() => setMobileView("tree")}
            >
              <ArrowLeft size={16} />
            </button>
            <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground overflow-hidden flex-1">
              <FileIcon size={13} className="shrink-0" />
              <span className="truncate">{selectedFile}</span>
            </div>
            {editorContent !== lastSavedRef.current && (
              <span className="flex items-center gap-1 text-xs text-yellow-500 font-mono shrink-0">
                <div className="w-1.5 h-1.5 rounded-full bg-yellow-500 animate-pulse" />
                Unsaved
              </span>
            )}
          </div>
          <div className="flex-1 overflow-auto">
            {isContentFetching && initializedRef.current !== selectedFile ? (
              <div className="flex items-center justify-center h-full text-muted-foreground font-mono text-sm">Loading…</div>
            ) : (
              <CodeMirror
                value={editorContent}
                height="100%"
                theme={oneDark}
                extensions={getExtensions()}
                onChange={(val) => setEditorContent(val)}
                className="h-full text-sm font-mono"
              />
            )}
          </div>
        </>
      ) : (
        <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
          <div className="w-14 h-14 rounded-2xl bg-sidebar border border-border flex items-center justify-center">
            <FileCode2 size={28} className="opacity-40" />
          </div>
          <p className="font-mono text-sm">Select a file to edit</p>
        </div>
      )}
    </div>
  );

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-background">

        {/* ── Desktop: side-by-side resizable panels ── */}
        <div className="hidden md:flex flex-1 overflow-hidden">
          <ResizablePanelGroup direction="horizontal" className="flex-1">
            <ResizablePanel defaultSize={28} minSize={18}>{FileTree}</ResizablePanel>
            <ResizableHandle className="w-px bg-border hover:bg-primary/50 transition-colors" />
            <ResizablePanel defaultSize={72}>{Editor}</ResizablePanel>
          </ResizablePanelGroup>
        </div>

        {/* ── Mobile: one panel at a time ── */}
        <div className="md:hidden flex-1 overflow-hidden">
          {mobileView === "tree" ? FileTree : Editor}
        </div>

      </div>

      {/* Dialog */}
      <Dialog open={dialogState.type !== "none"} onOpenChange={(open) => !open && closeDialog()}>
        <DialogContent className="max-w-sm sm:max-w-md font-mono mx-4">
          <DialogHeader>
            <DialogTitle>
              {dialogState.type === "new_file"   && "New File"}
              {dialogState.type === "new_folder" && "New Folder"}
              {dialogState.type === "rename"     && "Rename"}
              {dialogState.type === "move"       && "Move To"}
              {dialogState.type === "copy"       && "Copy To"}
              {dialogState.type === "delete"     && "Confirm Delete"}
            </DialogTitle>
          </DialogHeader>

          {dialogState.type !== "delete" && (
            <div className="py-3">
              <Input
                autoFocus
                value={dialogInput}
                onChange={(e) => setDialogInput(e.target.value)}
                placeholder={
                  dialogState.type === "rename" ? "New name…"
                  : dialogState.type === "move" || dialogState.type === "copy" ? "Destination path…"
                  : "Name…"
                }
                className="font-mono bg-background/50"
                onKeyDown={(e) => e.key === "Enter" && submitDialog()}
              />
            </div>
          )}

          {dialogState.type === "delete" && (
            <div className="py-3 text-sm">
              Delete <span className="text-primary font-bold">{(dialogState as any).path}</span>? This cannot be undone.
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={closeDialog}>Cancel</Button>
            <Button variant={dialogState.type === "delete" ? "destructive" : "default"} onClick={submitDialog}>
              {dialogState.type === "delete" ? "Delete" : "Confirm"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
}
