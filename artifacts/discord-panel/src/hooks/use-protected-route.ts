import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { useLocation } from "wouter";

export function useProtectedRoute() {
  const { isAuthenticated } = useAuth();
  const [, setLocation] = useLocation();

  useEffect(() => {
    if (!isAuthenticated) {
      setLocation("/login");
    }
  }, [isAuthenticated, setLocation]);

  return isAuthenticated;
}
