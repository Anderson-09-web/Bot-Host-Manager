import { useState } from "react";
import { useLocation } from "wouter";
import { useLogin } from "@workspace/api-client-react";
import { useAuth } from "@/lib/auth";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Bot, TerminalSquare } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const { setToken } = useAuth();
  const [, setLocation] = useLocation();
  const login = useLogin();
  const { toast } = useToast();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    login.mutate(
      { data: { username, password } },
      {
        onSuccess: (data) => {
          setToken(data.access_token);
          setLocation("/dashboard");
        },
        onError: () => {
          toast({
            title: "Access Denied",
            description: "Invalid credentials. Please try again.",
            variant: "destructive",
          });
        },
      }
    );
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background dark p-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center space-y-2">
          <div className="inline-flex w-16 h-16 rounded-xl bg-primary/10 items-center justify-center text-primary mb-4 ring-1 ring-primary/20 shadow-[0_0_30px_-5px_rgba(var(--primary),0.3)]">
            <TerminalSquare size={32} />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Mission Control</h1>
          <p className="text-muted-foreground">Authorize to manage your bot instance</p>
        </div>

        <Card className="border-border/50 bg-card/50 backdrop-blur-sm shadow-2xl">
          <form onSubmit={handleSubmit}>
            <CardContent className="pt-6 space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground/80 font-mono">USERNAME</label>
                <Input
                  required
                  autoFocus
                  placeholder="admin"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="bg-background/50 font-mono border-border/50 focus-visible:ring-primary/50"
                  data-testid="input-username"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground/80 font-mono">PASSWORD</label>
                <Input
                  required
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="bg-background/50 font-mono border-border/50 focus-visible:ring-primary/50"
                  data-testid="input-password"
                />
              </div>
            </CardContent>
            <CardFooter>
              <Button
                type="submit"
                className="w-full font-mono uppercase tracking-wider bg-primary hover:bg-primary/90 text-primary-foreground shadow-[0_0_15px_-3px_rgba(var(--primary),0.5)]"
                disabled={login.isPending}
                data-testid="button-submit"
              >
                {login.isPending ? "Authenticating..." : "Initialize Session"}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
}
