export const siteConfig = {
  name: "Voyantra",
  tagline: "Effortless trips, planned in seconds",
  description:
    "Voyantra plans extraordinary trips in seconds — real places pinned on the map, planned around the weather, with nothing made up. A day-by-day itinerary you can actually trust.",
  url: "https://voyantra.app",
  nav: [
    { title: "Features", href: "/features" },
    { title: "Pricing", href: "/pricing" },
    { title: "Enterprise", href: "/enterprise" },
    { title: "About", href: "/about" },
  ],
  footer: {
    Product: [
      { title: "Features", href: "/features" },
      { title: "Pricing", href: "/pricing" },
      { title: "Enterprise", href: "/enterprise" },
      { title: "Open the app", href: "/app" },
    ],
    Company: [
      { title: "About", href: "/about" },
      { title: "Contact", href: "/contact" },
      { title: "Careers", href: "/about#careers" },
    ],
    Legal: [
      { title: "Privacy", href: "/privacy" },
      { title: "Terms", href: "/terms" },
    ],
  },
} as const;
