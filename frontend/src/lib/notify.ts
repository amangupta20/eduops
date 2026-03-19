import { toast } from "@/hooks/use-toast";

export function notifySuccess(title: string, description?: string) {
  toast({
    title,
    description,
    variant: "success",
  });
}

export function notifyError(title: string, description?: string) {
  toast({
    title,
    description,
    variant: "destructive",
  });
}

export function notifyWarning(title: string, description?: string) {
  toast({
    title,
    description,
    variant: "warning",
  });
}
