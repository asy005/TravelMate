import { Loader2 } from "lucide-react";

interface PageLoaderProps {
  label?: string;
}

export const PageLoader = ({ label = "Loading..." }: PageLoaderProps) => {
  return (
    <div
      role="status"
      aria-live="polite"
      className="min-h-screen flex flex-col items-center justify-center gap-3"
    >
      <Loader2 className="h-8 w-8 animate-spin text-primary" aria-hidden="true" />
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  );
};
