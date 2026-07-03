"use client";

import { ArrowRight, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";

export function HeroSearch() {
  const router = useRouter();
  const [q, setQ] = React.useState("");

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        router.push("/signup");
      }}
      className="mx-auto mt-8 w-full max-w-xl"
    >
      <div className="flex items-center gap-2 rounded-2xl bg-white p-2 shadow-2xl">
        <Search className="ml-2 size-5 shrink-0 text-neutral-400" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Where to? Tokyo, Bali, Rome…"
          className="h-11 w-full min-w-0 bg-transparent text-neutral-900 placeholder:text-neutral-400 focus:outline-none"
        />
        <Button type="submit" variant="gradient" size="lg" className="shrink-0">
          Plan my trip <ArrowRight className="size-4" />
        </Button>
      </div>
    </form>
  );
}
