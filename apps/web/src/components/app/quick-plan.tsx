"use client";

import { ArrowRight, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";

export function QuickPlan({ className }: { className?: string }) {
  const router = useRouter();
  const [city, setCity] = React.useState("");

  function go(e: React.FormEvent) {
    e.preventDefault();
    const q = city.trim();
    router.push(q ? `/app/plan?mode=single&city=${encodeURIComponent(q)}` : "/app/plan");
  }

  return (
    <form onSubmit={go} className={className}>
      <div className="flex items-center gap-2 rounded-xl border border-white/25 bg-white/10 p-1.5 backdrop-blur-md">
        <Search className="ml-2 size-5 shrink-0 text-white/80" />
        <input
          value={city}
          onChange={(e) => setCity(e.target.value)}
          placeholder="Where do you want to go?"
          className="h-10 w-full min-w-0 bg-transparent text-white placeholder:text-white/70 focus:outline-none"
        />
        <Button type="submit" variant="gradient" className="shrink-0">
          Plan <ArrowRight className="size-4" />
        </Button>
      </div>
    </form>
  );
}
