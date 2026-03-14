"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

export default function LoginCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/");
    router.refresh();
  }, [router]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-950 px-6 text-zinc-100">
      <div className="flex items-center gap-3 rounded-2xl border border-zinc-800 bg-zinc-900/80 px-5 py-4">
        <Loader2 size={18} className="animate-spin text-zinc-400" />
        Returning to the preview...
      </div>
    </main>
  );
}
