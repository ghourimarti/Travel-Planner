const NAMES = ["Nomadly", "Wanderdesk", "Trippa", "Atlas Travel", "Voyage Labs", "Roamr"];

export function LogoCloud() {
  return (
    <section className="border-y border-border bg-muted/20">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <p className="text-center text-xs font-medium uppercase tracking-widest text-muted-foreground">
          Trusted by modern travel teams
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-x-10 gap-y-4">
          {NAMES.map((name) => (
            <span
              key={name}
              className="text-lg font-semibold tracking-tight text-muted-foreground/70 transition-colors hover:text-foreground"
            >
              {name}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
