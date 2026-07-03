/** Marketing copy/data — kept in one place so pages stay declarative. */

export const features = [
  {
    icon: "Zap",
    title: "Ready in seconds",
    body: "Tell us where you want to go and get a complete, day-by-day trip in under a minute — no blank pages, no hours of research.",
  },
  {
    icon: "MapPin",
    title: "Every place is real",
    body: "Restaurants, sights and neighborhoods that actually exist, pinned accurately on the map — so you never chase a spot that isn't there.",
  },
  {
    icon: "CloudSun",
    title: "Plans around the weather",
    body: "Your itinerary uses the forecast for your travel dates, so each day is arranged to make the most of the conditions.",
  },
  {
    icon: "Route",
    title: "Effortless multi-city trips",
    body: "Plan several cities in one go, with days ordered to keep travel time down and your whole trip flowing naturally.",
  },
  {
    icon: "ShieldCheck",
    title: "Double-checked for you",
    body: "Every plan is reviewed before you see it, so what you get is complete, sensible and ready to book.",
  },
  {
    icon: "Heart",
    title: "Made for how you travel",
    body: "Foodie, history buff, night owl or beach seeker — tell us what you love and every day is tailored to your taste.",
  },
] as const;

export const steps = [
  {
    n: "01",
    title: "Tell us your trip",
    body: "Choose your destinations, what you're into, and how long you're staying.",
  },
  {
    n: "02",
    title: "Watch it come together",
    body: "Your day-by-day plan builds in seconds, right in front of you — never a blank loading screen.",
  },
  {
    n: "03",
    title: "Go — everything's ready",
    body: "Get a complete itinerary of real places on a map, with weather and routes, ready to tweak or share.",
  },
] as const;

export const stats = [
  { value: "<1 min", label: "to a full itinerary" },
  { value: "5", label: "cities in one trip" },
  { value: "100%", label: "real places, nothing made up" },
  { value: "4.9★", label: "loved by travelers" },
] as const;

export const testimonials = [
  {
    quote:
      "It planned our four-city Japan trip in under a minute, and every single place was spot-on and easy to find. It saved us a whole weekend of research.",
    name: "Mara Lindqvist",
    role: "Frequent traveler",
  },
  {
    quote:
      "We added Voyantra to our own travel service and it just works. Our customers get accurate, ready-to-go itineraries — and we get happier travelers.",
    name: "Daniel Okafor",
    role: "VP Engineering, Wanderdesk",
  },
  {
    quote:
      "Finally, a trip planner that doesn't send you to restaurants that closed years ago. Everything it suggests is real. That's the trust travelers want.",
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
      "Up to 10 trips a month",
      "Single & multi-city planning",
      "Interactive map & live planning",
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
      "Unlimited trips",
      "Priority planning — skip the queue",
      "Map, export & sharing tools",
      "Your full trip history",
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
    description: "For businesses adding trip planning to their own product.",
    features: [
      "Add trip planning to your product (API)",
      "Single sign-on & team accounts",
      "Usage limits & predictable billing",
      "Plan around your own places & inventory",
      "Dedicated support & uptime guarantee",
    ],
    cta: "Talk to sales",
    href: "/enterprise",
    highlighted: false,
  },
] as const;

export const faqs = [
  {
    q: "Are the places real, or does it make things up?",
    a: "Every recommendation is a real, verified place, pinned accurately on the map. Before you ever see a plan, it's reviewed to remove anything that doesn't check out — so you're never sent somewhere that doesn't exist.",
  },
  {
    q: "How fast is it?",
    a: "A single city usually takes just a few seconds, and a full multi-city trip is typically ready in under a minute. You can watch it build in real time, so there's never a blank loading screen.",
  },
  {
    q: "Can I add Voyantra to my own product?",
    a: "Yes. Our Enterprise plan lets you offer the same trip planning inside your own app or website, with single sign-on, usage controls and dedicated support.",
  },
  {
    q: "How much does it cost?",
    a: "Start free with up to 10 trips a month. Pro is $29/month for unlimited planning, and Enterprise is custom-priced for businesses — talk to us for a quote.",
  },
  {
    q: "Is my data private?",
    a: "We keep only what we need to plan your trips, and you can delete your data anytime. Business plans include full account isolation.",
  },
] as const;
