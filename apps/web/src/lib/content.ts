/** Marketing copy/data — kept in one place so pages stay declarative. */

export const features = [
  {
    icon: "Bot",
    title: "Multi-agent planning",
    body: "A coordinator dispatches per-city worker agents and a critic that validates every draft — not a single prompt, but a supervised team with a corrective loop.",
  },
  {
    icon: "MapPin",
    title: "Grounded in real places",
    body: "Every stop resolves to a real POI with coordinates from live geocoding and OpenStreetMap — no hallucinated restaurants, no invented landmarks.",
  },
  {
    icon: "CloudSun",
    title: "Live weather & routing",
    body: "Forecasts and inter-city travel legs are pulled at plan time, so the itinerary reflects the world as it actually is on your travel dates.",
  },
  {
    icon: "Route",
    title: "Multi-city trips",
    body: "Plan up to five cities across ten days in a single run, with optimized inter-city transitions and per-city day plans.",
  },
  {
    icon: "ShieldCheck",
    title: "Cited & trustworthy",
    body: "A critic agent flags invented places and gaps before you ever see them. Itineraries come with the evidence behind each recommendation.",
  },
  {
    icon: "Gauge",
    title: "Fast & cost-controlled",
    body: "Tiered models, caching and hard per-run budgets keep latency low and cost under control — typically a fraction of a cent per itinerary.",
  },
] as const;

export const steps = [
  {
    n: "01",
    title: "Tell us where & what you love",
    body: "Pick your cities, interests and trip length. Voyantra turns that into a structured planning request.",
  },
  {
    n: "02",
    title: "Watch the agents work",
    body: "Follow a live trace as agents geocode, gather real data, compose and critique — fully transparent, step by step.",
  },
  {
    n: "03",
    title: "Get a grounded itinerary",
    body: "Receive a day-by-day plan of real, mapped places with weather and routes — ready to refine or export.",
  },
] as const;

export const stats = [
  { value: "5", label: "cities per trip" },
  { value: "<45s", label: "p95 full itinerary" },
  { value: "99.5%", label: "uptime SLO" },
  { value: "<$0.01", label: "typical cost / itinerary" },
] as const;

export const testimonials = [
  {
    quote:
      "It planned a 4-city Japan trip in under a minute, and every single place was real and well-located. The live agent trace sold our whole team.",
    name: "Mara Lindqvist",
    role: "Head of Product, Nomadly",
  },
  {
    quote:
      "We replaced a manual travel-desk workflow with Voyantra's API. Grounded itineraries, predictable cost, and an audit trail for every plan.",
    name: "Daniel Okafor",
    role: "VP Engineering, Wanderdesk",
  },
  {
    quote:
      "The critic agent catching invented restaurants before they reach the customer is exactly the trust layer travel AI has been missing.",
    name: "Priya Nair",
    role: "Founder, Trippa",
  },
] as const;

export const pricingTiers = [
  {
    name: "Explorer",
    price: "Free",
    period: "",
    description: "For trying Voyantra and planning your own trips.",
    features: [
      "Up to 10 itineraries / month",
      "Single & multi-city planning",
      "Live agent trace",
      "Community support",
    ],
    cta: "Start free",
    href: "/app",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "$29",
    period: "/mo",
    description: "For frequent travelers and small travel businesses.",
    features: [
      "Unlimited itineraries",
      "Priority planning queue",
      "Map & export tools",
      "Itinerary history & sharing",
      "Email support",
    ],
    cta: "Go Pro",
    href: "/app",
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "For platforms embedding planning at scale.",
    features: [
      "API access & higher rate limits",
      "SSO / Auth0 & multi-tenancy",
      "Per-tenant quotas & audit logs",
      "Custom POI corpora",
      "SLA & dedicated support",
    ],
    cta: "Talk to sales",
    href: "/enterprise",
    highlighted: false,
  },
] as const;

export const faqs = [
  {
    q: "How does Voyantra avoid hallucinated places?",
    a: "Every recommendation is grounded: cities are geocoded to real coordinates and points of interest come from OpenStreetMap and live data sources. A dedicated critic agent then reviews each draft and flags any invented place before you see it.",
  },
  {
    q: "How fast is it?",
    a: "A single-city plan typically returns in a few seconds; a full multi-city trip targets a p95 under 45 seconds. You watch the agents work in real time, so there's never a blank loading screen.",
  },
  {
    q: "Can I embed Voyantra in my own product?",
    a: "Yes. The Enterprise plan exposes the same multi-agent planning engine via API, with Auth0 SSO, per-tenant quotas, rate limiting and audit logs designed for multi-tenant platforms.",
  },
  {
    q: "What does it cost to run?",
    a: "Voyantra uses tiered models, aggressive caching and hard per-run budgets. A typical itinerary costs a fraction of a cent in model spend, and every run is capped so cost can never run away.",
  },
  {
    q: "Is my data private?",
    a: "We minimize what we store, redact PII from logs, and provide a data-deletion path. Enterprise deployments support full tenant isolation.",
  },
] as const;
