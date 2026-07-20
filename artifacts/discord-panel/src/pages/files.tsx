import { useState, useRef, useEffect } from "react";
import { useProtectedRoute } from "@/hooks/use-protected-route";
import { AppLayout } from "@/components/layout";
import {
  useListFiles,
  useDeleteFile,
  useGetFileContent,
  useUpdateFileContent,
  useCreateFile,
  useRenameFile,
  useMoveFile,
  useCopyFile,
  getListFilesQueryKey,
  getGetFileContentQueryKey
} from "@workspace/api-client-react";
import { useAuth } from "@/lib/auth";
import { useQueryClient } from "@tanstack/react-query";
import { 
  Folder, File as FileIcon, FileCode2, FileJson, FileText, Image as ImageIcon,
  Upload, Plus, RefreshCw, Download, Trash2, Edit2, Pencil, Copy, MoveRight, ChevronRight, Save, X, FolderPlus
} from "lucide-react";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { json } from '@codemirror/lang-json';
import { oneDark } from '@codemirror/theme-one-dark';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

const getFileIcon = (filename: string, isFolder: boolean) => {
  if (isFolder) return <Folder size={18} className="text-blue-400 fill-blue-400/20" />;
  if (filename.endsWith(".py")) return <FileCode2 size={18} className="text-yellow-400" />;
  if (filename.endsWith(".json")) return <FileJson size={18} className="text-green-400" />;
  if (filename.match(/\.(png|jpg|jpeg|gif|ico|webp)$/i)) return <ImageIcon size={18} className="text-purple-400" />;
  return <FileText size={18} className="text-muted-foreground" />;
};

type DialogState = 
  | { type: 'none' }
  | { type: 'new_file', basePath: string }
  | { type: 'new_folder', basePath: string }
  | { type: 'rename', path: string, currentName: string }
  | { type: 'move', path: string }
  | { type: 'copy', path: string }
  | { type: 'delete', path: string };

export default function Files() {
  useProtectedRoute();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { token } = useAuth();
  
  const [currentPath, setCurrentPath] = useState("/");
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [editorContent, setEditorContent] = useState("");
  const [dialogState, setDialogState] = useState<DialogState>({ type: 'none' });
  const [dialogInput, setDialogInput] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Queries
  const { data: fileList, isLoading: isListLoading, refetch: refetchList } = useListFiles(
    { path: currentPath === "/" ? "" : currentPath }, 
    { query: { queryKey: getListFilesQueryKey({ path: currentPath === "/" ? "" : currentPath }) } }
  );

  const { data: fileContent, isFetching: isContentFetching } = useGetFileContent(
    { path: selectedFilePath || "" },
    { query: { enabled: !!selectedFilePath, queryKey: getGetFileContentQueryKey({ path: selectedFilePath || "" }) } }
  );

  // Mutations
  const updateFileContent = useUpdateFileContent();
  const deleteFile = useDeleteFile();
  const createFile = useCreateFile();
  const renameFile = useRenameFile();
  const moveFile = useMoveFile();
  const copyFile = useCopyFile();

  // Auto-save logic
  const initializedForPath = useRef<string | null>(null);
  const lastSaved = useRef<string>("");
  const mutateFnRef = useRef(updateFileContent.mutate);
  mutateFnRef.current = updateFileContent.mutate;

  useEffect(() => {
    if (fileContent && selectedFilePath && initializedForPath.current !== selectedFilePath) {
      initializedForPath.current = selectedFilePath;
      setEditorContent(fileContent.content);
      lastSaved.current = fileContent.content;
    }
  }, [fileContent, selectedFilePath]);

  useEffect(() => {
    if (!selectedFilePath || initializedForPath.current !== selectedFilePath) return;
    
    const timer = setTimeout(() => {
      if (editorContent !== lastSaved.current) {
        mutateFnRef.current({
          data: { path: selectedFilePath, content: editorContent }
        }, {
          onSuccess: () => {
            lastSaved.current = editorContent;
            // Silent save
            queryClient.setQueryData(getGetFileContentQueryKey({ path: selectedFilePath }), (old: any) => 
              old ? { ...old, content: editorContent } : old
            );
          },
          onError: (e: any) => {
            toast({ title: "Save Failed", description: e.message, variant: "destructive" });
          }
        });
      }
    }, 1000);
    return () => clearTimeout(timer);
  }, [editorContent, selectedFilePath, queryClient]);

  // Actions
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    const file = e.target.files[0];
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('path', currentPath === "/" ? "" : currentPath);

    try {
      const res = await fetch('/api/files/upload', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });
      if (!res.ok) throw new Error("Upload failed");
      toast({ title: "Success", description: "File uploaded successfully" });
      refetchList();
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    }
    
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDownload = (path: string) => {
    window.open(`/api/files/download?path=${encodeURIComponent(path)}&token=${token}`, '_blank');
  };

  const closeDialog = () => {
    setDialogState({ type: 'none' });
    setDialogInput("");
  };

  const submitDialog = () => {
    if (dialogState.type === 'none') return;

    if (dialogState.type === 'new_file') {
      const path = currentPath === "/" ? dialogInput : `${currentPath}/${dialogInput}`;
      createFile.mutate({ data: { path, type: 'file', content: "" } }, {
        onSuccess: () => { refetchList(); closeDialog(); }
      });
    } else if (dialogState.type === 'new_folder') {
      const path = currentPath === "/" ? dialogInput : `${currentPath}/${dialogInput}`;
      createFile.mutate({ data: { path, type: 'folder' } }, {
        onSuccess: () => { refetchList(); closeDialog(); }
      });
    } else if (dialogState.type === 'rename') {
      renameFile.mutate({ data: { path: dialogState.path, new_name: dialogInput } }, {
        onSuccess: () => { 
          if (selectedFilePath === dialogState.path) setSelectedFilePath(null);
          refetchList(); 
          closeDialog(); 
        }
      });
    } else if (dialogState.type === 'move') {
      moveFile.mutate({ data: { source: dialogState.path, destination: dialogInput } }, {
        onSuccess: () => { refetchList(); closeDialog(); }
      });
    } else if (dialogState.type === 'copy') {
      copyFile.mutate({ data: { source: dialogState.path, destination: dialogInput } }, {
        onSuccess: () => { refetchList(); closeDialog(); }
      });
    } else if (dialogState.type === 'delete') {
      deleteFile.mutate({ params: { path: dialogState.path } }, {
        onSuccess: () => { 
          if (selectedFilePath === dialogState.path) setSelectedFilePath(null);
          refetchList(); 
          closeDialog(); 
        }
      });
    }
  };

  const navigateUp = () => {
    if (currentPath === "/") return;
    const parts = currentPath.split("/");
    parts.pop();
    setCurrentPath(parts.length ? parts.join("/") : "/");
  };

  const breadcrumbs = currentPath.split("/").filter(Boolean);

  const getExtensions = () => {
    if (!selectedFilePath) return [];
    if (selectedFilePath.endsWith('.py')) return [python()];
    if (selectedFilePath.endsWith('.json')) return [json()];
    return [];
  };

  return (
    <AppLayout>
      <div className="flex flex-col h-full bg-background">
        
        {/* Toolbar */}
        <div className="flex items-center justify-between p-3 border-b border-border bg-card/50 shrink-0">
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setDialogState({ type: 'new_file', basePath: currentPath })}>
              <FileIcon size={14} className="mr-2" /> New File
            </Button>
            <Button variant="outline" size="sm" onClick={() => setDialogState({ type: 'new_folder', basePath: currentPath })}>
              <FolderPlus size={14} className="mr-2" /> New Folder
            </Button>
            <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
              <Upload size={14} className="mr-2" /> Upload
              <input type="file" className="hidden" ref={fileInputRef} onChange={handleUpload} />
            </Button>
            <div className="w-px h-6 bg-border mx-2" />
            <Button variant="ghost" size="sm" onClick={() => refetchList()}>
              <RefreshCw size={14} className={isListLoading ? "animate-spin" : ""} />
            </Button>
          </div>
          
          <div className="flex items-center text-sm font-mono text-muted-foreground gap-1 px-3">
            <span className="cursor-pointer hover:text-primary transition-colors" onClick={() => setCurrentPath("/")}>root</span>
            {breadcrumbs.map((part, i) => {
              const path = "/" + breadcrumbs.slice(0, i + 1).join("/");
              return (
                <span key={path} className="flex items-center gap-1">
                  <ChevronRight size={14} />
                  <span className="cursor-pointer hover:text-primary transition-colors" onClick={() => setCurrentPath(path)}>
                    {part}
                  </span>
                </span>
              );
            })}
          </div>
        </div>

        <ResizablePanelGroup direction="horizontal" className="flex-1">
          <ResizablePanel defaultSize={30} minSize={20} className="flex flex-col bg-sidebar">
            <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
              {currentPath !== "/" && (
                <div 
                  className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted cursor-pointer text-sm font-mono text-muted-foreground"
                  onClick={navigateUp}
                >
                  <Folder size={18} className="text-blue-400/50" />
                  <span>..</span>
                </div>
              )}
              
              {fileList?.items.map(item => (
                <ContextMenu key={item.path}>
                  <ContextMenuTrigger>
                    <div 
                      className={`flex items-center justify-between px-2 py-1.5 rounded cursor-pointer text-sm font-mono group transition-colors ${
                        selectedFilePath === item.path ? 'bg-primary/20 text-primary' : 'hover:bg-muted'
                      }`}
                      onClick={() => {
                        if (item.type === 'folder') {
                          setCurrentPath(item.path);
                        } else {
                          setSelectedFilePath(item.path);
                        }
                      }}
                    >
                      <div className="flex items-center gap-2 overflow-hidden">
                        {getFileIcon(item.name, item.type === 'folder')}
                        <span className="truncate">{item.name}</span>
                      </div>
                      <span className="text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
                        {item.type === 'file' && item.size ? `${(item.size / 1024).toFixed(1)}KB` : ''}
                      </span>
                    </div>
                  </ContextMenuTrigger>
                  <ContextMenuContent className="w-48 font-mono text-sm">
                    {item.type === 'file' && (
                      <ContextMenuItem onClick={() => setSelectedFilePath(item.path)}>
                        <Edit2 size={14} className="mr-2" /> Edit
                      </ContextMenuItem>
                    )}
                    <ContextMenuItem onClick={() => setDialogState({ type: 'rename', path: item.path, currentName: item.name })}>
                      <Pencil size={14} className="mr-2" /> Rename
                    </ContextMenuItem>
                    <ContextMenuItem onClick={() => setDialogState({ type: 'move', path: item.path })}>
                      <MoveRight size={14} className="mr-2" /> Move
                    </ContextMenuItem>
                    <ContextMenuItem onClick={() => setDialogState({ type: 'copy', path: item.path })}>
                      <Copy size={14} className="mr-2" /> Copy
                    </ContextMenuItem>
                    {item.type === 'file' && (
                      <ContextMenuItem onClick={() => handleDownload(item.path)}>
                        <Download size={14} className="mr-2" /> Download
                      </ContextMenuItem>
                    )}
                    <ContextMenuSeparator />
                    <ContextMenuItem 
                      className="text-destructive focus:bg-destructive focus:text-destructive-foreground"
                      onClick={() => setDialogState({ type: 'delete', path: item.path })}
                    >
                      <Trash2 size={14} className="mr-2" /> Delete
                    </ContextMenuItem>
                  </ContextMenuContent>
                </ContextMenu>
              ))}
              
              {fileList?.items.length === 0 && (
                <div className="text-center text-muted-foreground text-sm py-8 font-mono">
                  Empty directory
                </div>
              )}
            </div>
          </ResizablePanel>

          <ResizableHandle className="w-1 bg-border hover:bg-primary/50 transition-colors" />

          <ResizablePanel defaultSize={70} className="flex flex-col bg-[#282c34]">
            {selectedFilePath ? (
              <div className="flex flex-col h-full relative">
                <div className="flex items-center justify-between px-4 py-2 bg-sidebar border-b border-border shrink-0">
                  <div className="flex items-center gap-2 font-mono text-sm text-muted-foreground">
                    <FileIcon size={14} />
                    <span>{selectedFilePath}</span>
                  </div>
                  {editorContent !== lastSaved.current && (
                    <span className="flex items-center gap-1 text-xs text-yellow-500 font-mono">
                      <div className="w-1.5 h-1.5 rounded-full bg-yellow-500 animate-pulse" />
                      Unsaved
                    </span>
                  )}
                </div>
                <div className="flex-1 overflow-auto">
                  {isContentFetching && initializedForPath.current !== selectedFilePath ? (
                    <div className="flex items-center justify-center h-full text-muted-foreground font-mono">
                      Loading content...
                    </div>
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
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-4">
                <div className="w-16 h-16 rounded-2xl bg-sidebar border border-border flex items-center justify-center">
                  <FileCode2 size={32} className="opacity-50" />
                </div>
                <p className="font-mono text-sm">Select a file to view or edit</p>
              </div>
            )}
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>

      <Dialog open={dialogState.type !== 'none'} onOpenChange={(open) => !open && closeDialog()}>
        <DialogContent className="sm:max-w-md font-mono">
          <DialogHeader>
            <DialogTitle>
              {dialogState.type === 'new_file' && 'Create New File'}
              {dialogState.type === 'new_folder' && 'Create New Folder'}
              {dialogState.type === 'rename' && 'Rename'}
              {dialogState.type === 'move' && 'Move to Path'}
              {dialogState.type === 'copy' && 'Copy to Path'}
              {dialogState.type === 'delete' && 'Confirm Deletion'}
            </DialogTitle>
          </DialogHeader>
          
          {dialogState.type !== 'delete' && (
            <div className="py-4">
              <Input
                autoFocus
                value={dialogInput}
                onChange={e => setDialogInput(e.target.value)}
                placeholder={
                  dialogState.type === 'rename' ? 'New name...' : 
                  (dialogState.type === 'move' || dialogState.type === 'copy') ? 'Destination path...' :
                  'Name...'
                }
                className="font-mono bg-background/50"
                onKeyDown={(e) => e.key === 'Enter' && submitDialog()}
              />
            </div>
          )}
          
          {dialogState.type === 'delete' && (
            <div className="py-4 text-sm">
              Are you sure you want to delete <span className="text-primary font-bold">{dialogState.path}</span>?
              This action cannot be undone.
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>Cancel</Button>
            <Button 
              variant={dialogState.type === 'delete' ? 'destructive' : 'default'}
              onClick={submitDialog}
            >
              {dialogState.type === 'delete' ? 'Delete' : 'Confirm'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
}
