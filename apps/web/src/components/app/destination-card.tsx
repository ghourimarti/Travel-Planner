import { ArrowRight, MapPin, Sparkles, Star } from "lucide-react";
import Link from "next/link";

import {
  type Destination,
  destImage,
  isFeatured,
  ratingFor,
  reviewsFor,
} from "@/lib/destinations";
import { cn } from "@/lib/utils";

export function DestinationCard({
  dest,
  className,
  priority,
  href,
}: {
  dest: Destination;
  className?: string;
  priority?: boolean;
  href?: string;
}) {
  const rating = ratingFor(dest.slug);
  const reviews = reviewsFor(dest.slug);
  const featured = isFeatured(dest.slug);

  return (
    <Link
      href={href ?? `/app/destinations/${dest.slug}`}
      className={cn(
        "group flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm transition-all hover:-translate-y-1 hover:shadow-xl",
        className,
      )}
    >
      {/* Photo */}
      <div className="relative aspect-[4/3] w-full overflow-hidden">
        <img
          src={destImage(dest.photoId, 800)}
          alt={dest.name}
          loading={priority ? "eager" : "lazy"}
          className="size-full object-cover transition-transform duration-700 ease-out group-hover:scale-110"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent" />

        {featured && (
          <span className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-[linear-gradient(100deg,var(--color-brand-1),var(--color-brand-2))] px-2.5 py-1 text-[11px] font-semibold text-white shadow-md">
            <Sparkles className="size-3" /> Featured
          </span>
        )}
        <span className="absolute right-3 top-3 inline-flex items-center gap-1 rounded-full bg-white/95 px-2 py-1 text-[11px] font-bold text-foreground shadow-md">
          <Star className="size-3 fill-amber-400 text-amber-400" /> {rating}
        </span>

        <div className="absolute inset-x-0 bottom-0 p-4 text-white">
          <p className="flex items-center gap-1 text-xs font-medium opacity-95">
            <MapPin className="size-3" /> {dest.country}
          </p>
          <h3 className="mt-0.5 text-xl font-bold leading-tight drop-shadow-sm">{dest.name}</h3>
        </div>
      </div>

      {/* Info footer (tour-card style) */}
      <div className="flex flex-1 flex-col p-4">
        <p className="line-clamp-2 text-sm text-muted-foreground">{dest.blurb}</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {dest.tags.slice(0, 3).map((t) => (
            <span
              key={t}
              className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
            >
              {t}
            </span>
          ))}
        </div>
        <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
          <div className="text-xs text-muted-foreground">
            <span className="font-semibold text-foreground">{dest.highlights.length}</span> highlights
            <span className="mx-1">·</span>
            <span className="text-foreground/70">{reviews} reviews</span>
          </div>
          <span className="inline-flex items-center gap-1 text-sm font-semibold text-primary transition-transform group-hover:translate-x-0.5">
            Plan <ArrowRight className="size-4" />
          </span>
        </div>
      </div>
    </Link>
  );
}
