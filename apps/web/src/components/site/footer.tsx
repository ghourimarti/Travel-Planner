import Link from "next/link";

import { Logo } from "@/components/site/logo";
import { siteConfig } from "@/lib/site";

export function Footer() {
  return (
    <footer className="border-t border-border bg-muted/30">
      <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-10 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <Logo />
            <p className="mt-4 max-w-xs text-sm text-muted-foreground">{siteConfig.description}</p>
            <p className="mt-6 text-xs text-muted-foreground">
              Real places only · planned around the weather · ready in seconds
            </p>
          </div>

          {Object.entries(siteConfig.footer).map(([group, links]) => (
            <div key={group}>
              <h4 className="text-sm font-semibold">{group}</h4>
              <ul className="mt-4 space-y-3">
                {links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {link.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-border pt-8 text-sm text-muted-foreground sm:flex-row">
          <p>
            © {new Date().getFullYear()} {siteConfig.name}. All rights reserved.
          </p>
          <p>Real places, mapped and double-checked — your next adventure, planned in seconds.</p>
        </div>
      </div>
    </footer>
  );
}
