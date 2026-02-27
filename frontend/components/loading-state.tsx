interface LoadingStateProps {
  message?: string;
  className?: string;
}

export function LoadingState({ message = "Chargement...", className }: LoadingStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center py-20 ${className || ""}`}>
      <div className="h-6 w-6 rounded-full border-2 border-violet-200 border-t-violet-600 animate-spin" />
      <span className="mt-3 text-sm text-muted-foreground">{message}</span>
    </div>
  );
}
