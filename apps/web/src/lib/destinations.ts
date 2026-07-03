/**
 * Curated destination catalogue — powers the imagery and Discover experience.
 * Photos are stable Unsplash CDN URLs (keyless). `interests` align with the plan
 * form's vocabulary so "Plan a trip here" can pre-fill the planner.
 */

export interface Destination {
  slug: string;
  name: string;
  country: string;
  region: "Asia" | "Europe" | "Americas" | "Africa" | "Oceania" | "Middle East";
  photoId: string;
  blurb: string;
  tags: string[];
  interests: string[];
  bestSeason: string;
  highlights: string[];
}

/** Build a sized Unsplash CDN URL for a destination photo. */
export function destImage(photoId: string, w = 800): string {
  return `https://images.unsplash.com/${photoId}?auto=format&fit=crop&w=${w}&q=80`;
}

export const destinations: Destination[] = [
  {
    slug: "tokyo",
    name: "Tokyo",
    country: "Japan",
    region: "Asia",
    photoId: "photo-1540959733332-eab4deabeeaf",
    blurb:
      "A dazzling collision of neon-lit futurism and centuries-old tradition — temples beside skyscrapers, and the best food city on earth.",
    tags: ["Culture", "Food", "Nightlife"],
    interests: ["food", "temples", "shopping"],
    bestSeason: "Mar–May (cherry blossom) & Oct–Nov",
    highlights: ["Senso-ji Temple", "Shibuya Crossing", "Tsukiji Outer Market", "TeamLab Planets"],
  },
  {
    slug: "kyoto",
    name: "Kyoto",
    country: "Japan",
    region: "Asia",
    photoId: "photo-1493976040374-85c8e12f0c0e",
    blurb:
      "Japan's serene former capital: thousands of shrines, golden pavilions, bamboo groves and geisha districts.",
    tags: ["Temples", "Nature", "History"],
    interests: ["temples", "nature", "history"],
    bestSeason: "Apr (blossom) & Nov (autumn leaves)",
    highlights: ["Fushimi Inari Shrine", "Arashiyama Bamboo Grove", "Kinkaku-ji", "Gion District"],
  },
  {
    slug: "paris",
    name: "Paris",
    country: "France",
    region: "Europe",
    photoId: "photo-1502602898657-3e91760cbb34",
    blurb:
      "The city of light — world-class art, café culture, grand boulevards and a skyline crowned by the Eiffel Tower.",
    tags: ["Art", "History", "Food"],
    interests: ["art", "history", "food"],
    bestSeason: "Apr–Jun & Sep–Oct",
    highlights: ["Louvre Museum", "Eiffel Tower", "Montmartre", "Musée d'Orsay"],
  },
  {
    slug: "rome",
    name: "Rome",
    country: "Italy",
    region: "Europe",
    photoId: "photo-1552832230-c0197dd311b5",
    blurb:
      "An open-air museum where ancient ruins, Renaissance art and unforgettable cuisine share every cobblestone street.",
    tags: ["History", "Food", "Architecture"],
    interests: ["history", "food", "architecture"],
    bestSeason: "Apr–Jun & Sep–Oct",
    highlights: ["Colosseum", "Vatican Museums", "Trevi Fountain", "Trastevere"],
  },
  {
    slug: "new-york",
    name: "New York",
    country: "United States",
    region: "Americas",
    photoId: "photo-1496442226666-8d4d0e62e6e9",
    blurb:
      "The city that never sleeps — iconic skylines, world-class museums, Broadway and a food scene from every corner of the globe.",
    tags: ["City", "Nightlife", "Art"],
    interests: ["museums", "nightlife", "shopping"],
    bestSeason: "Apr–Jun & Sep–Nov",
    highlights: ["Central Park", "The Met", "Brooklyn Bridge", "Times Square"],
  },
  {
    slug: "bali",
    name: "Bali",
    country: "Indonesia",
    region: "Asia",
    photoId: "photo-1537996194471-e657df975ab4",
    blurb:
      "Island of the gods — emerald rice terraces, surf beaches, clifftop temples and a deeply spiritual culture.",
    tags: ["Beaches", "Nature", "Wellness"],
    interests: ["beaches", "nature", "temples"],
    bestSeason: "Apr–Oct (dry season)",
    highlights: ["Uluwatu Temple", "Tegallalang Rice Terraces", "Ubud", "Seminyak Beach"],
  },
  {
    slug: "london",
    name: "London",
    country: "United Kingdom",
    region: "Europe",
    photoId: "photo-1513635269975-59663e0ac1ad",
    blurb:
      "Royal history meets cutting-edge culture — world-class (and free) museums, historic pubs and endless neighborhoods to explore.",
    tags: ["History", "Museums", "Theatre"],
    interests: ["museums", "history", "shopping"],
    bestSeason: "May–Sep",
    highlights: ["British Museum", "Tower of London", "West End", "Borough Market"],
  },
  {
    slug: "barcelona",
    name: "Barcelona",
    country: "Spain",
    region: "Europe",
    photoId: "photo-1583422409516-2895a77efded",
    blurb:
      "Gaudí's surreal architecture, Mediterranean beaches, tapas bars and a buzzing nightlife that runs till dawn.",
    tags: ["Architecture", "Beaches", "Food"],
    interests: ["architecture", "beaches", "food"],
    bestSeason: "May–Jun & Sep",
    highlights: ["Sagrada Família", "Park Güell", "Gothic Quarter", "La Boqueria"],
  },
  {
    slug: "dubai",
    name: "Dubai",
    country: "United Arab Emirates",
    region: "Middle East",
    photoId: "photo-1512453979798-5ea266f8880c",
    blurb:
      "Futuristic ambition in the desert — record-breaking towers, luxury shopping, golden dunes and beach resorts.",
    tags: ["Luxury", "Shopping", "Architecture"],
    interests: ["shopping", "architecture", "nightlife"],
    bestSeason: "Nov–Mar",
    highlights: ["Burj Khalifa", "Dubai Mall", "Desert Safari", "Palm Jumeirah"],
  },
  {
    slug: "singapore",
    name: "Singapore",
    country: "Singapore",
    region: "Asia",
    photoId: "photo-1525625293386-3f8f99389edd",
    blurb:
      "A garden city of the future — hawker food, futuristic super-trees, and a melting pot of cultures on every block.",
    tags: ["City", "Food", "Nature"],
    interests: ["food", "nature", "shopping"],
    bestSeason: "Feb–Apr",
    highlights: ["Gardens by the Bay", "Marina Bay Sands", "Hawker Centres", "Sentosa"],
  },
  {
    slug: "istanbul",
    name: "Istanbul",
    country: "Türkiye",
    region: "Europe",
    photoId: "photo-1524231757912-21f4fe3a7200",
    blurb:
      "Where Europe meets Asia — Byzantine domes, Ottoman palaces, spice-scented bazaars and Bosphorus sunsets.",
    tags: ["History", "Culture", "Food"],
    interests: ["history", "architecture", "food"],
    bestSeason: "Apr–May & Sep–Nov",
    highlights: ["Hagia Sophia", "Blue Mosque", "Grand Bazaar", "Bosphorus Cruise"],
  },
  {
    slug: "sydney",
    name: "Sydney",
    country: "Australia",
    region: "Oceania",
    photoId: "photo-1506973035872-a4ec16b8e8d9",
    blurb:
      "Harbour city perfection — the iconic Opera House, golden beaches, coastal walks and a laid-back outdoor lifestyle.",
    tags: ["Beaches", "Nature", "City"],
    interests: ["beaches", "nature", "food"],
    bestSeason: "Sep–Nov & Mar–May",
    highlights: ["Sydney Opera House", "Bondi Beach", "Harbour Bridge", "Blue Mountains"],
  },
  {
    slug: "marrakech",
    name: "Marrakech",
    country: "Morocco",
    region: "Africa",
    photoId: "photo-1538970272646-f61fabb3a8a2",
    blurb:
      "A feast for the senses — labyrinthine souks, ornate palaces, rooftop terraces and the buzz of Jemaa el-Fnaa.",
    tags: ["Culture", "History", "Food"],
    interests: ["history", "shopping", "food"],
    bestSeason: "Mar–May & Sep–Nov",
    highlights: ["Jemaa el-Fnaa", "Bahia Palace", "Majorelle Garden", "The Medina"],
  },
  {
    slug: "reykjavik",
    name: "Reykjavik",
    country: "Iceland",
    region: "Europe",
    photoId: "photo-1558642452-9d2a7deb7f62",
    blurb:
      "Gateway to fire and ice — northern lights, geothermal lagoons, waterfalls and otherworldly volcanic landscapes.",
    tags: ["Nature", "Adventure"],
    interests: ["nature", "history"],
    bestSeason: "Jun–Aug (midnight sun) & Sep–Mar (auroras)",
    highlights: ["Blue Lagoon", "Golden Circle", "Northern Lights", "Hallgrímskirkja"],
  },
  {
    slug: "lisbon",
    name: "Lisbon",
    country: "Portugal",
    region: "Europe",
    photoId: "photo-1555992336-fb0d29498b13",
    blurb:
      "Sun-drenched hills, pastel facades, rattling trams and soulful fado — Europe's most charming coastal capital.",
    tags: ["Architecture", "Food", "Coastal"],
    interests: ["architecture", "food", "history"],
    bestSeason: "Mar–Jun & Sep–Oct",
    highlights: ["Belém Tower", "Alfama", "Tram 28", "Time Out Market"],
  },
  {
    slug: "hong-kong",
    name: "Hong Kong",
    country: "China",
    region: "Asia",
    photoId: "photo-1473951574080-01fe45ec8643",
    blurb:
      "A vertical city of dazzling skylines, dim sum palaces, mountain trails and neon-soaked night markets.",
    tags: ["City", "Food", "Nature"],
    interests: ["food", "shopping", "nature"],
    bestSeason: "Oct–Dec",
    highlights: ["Victoria Peak", "Temple Street Market", "Tian Tan Buddha", "Star Ferry"],
  },
  {
    slug: "amsterdam",
    name: "Amsterdam",
    country: "Netherlands",
    region: "Europe",
    photoId: "photo-1518105779142-d975f22f1b0a",
    blurb:
      "Golden-age canals, world-class art, bicycle culture and an effortlessly relaxed, open-minded atmosphere.",
    tags: ["Art", "History", "Canals"],
    interests: ["museums", "art", "history"],
    bestSeason: "Apr–May & Sep–Oct",
    highlights: ["Rijksmuseum", "Van Gogh Museum", "Anne Frank House", "Jordaan Canals"],
  },
  {
    slug: "bangkok",
    name: "Bangkok",
    country: "Thailand",
    region: "Asia",
    photoId: "photo-1504512485720-7d83a16ee930",
    blurb:
      "Frenetic, golden and delicious — glittering temples, floating markets, rooftop bars and legendary street food.",
    tags: ["Temples", "Food", "Nightlife"],
    interests: ["temples", "food", "nightlife"],
    bestSeason: "Nov–Feb",
    highlights: ["Grand Palace", "Wat Arun", "Chatuchak Market", "Khao San Road"],
  },
  {
    slug: "cape-town",
    name: "Cape Town",
    country: "South Africa",
    region: "Africa",
    photoId: "photo-1605130284535-11dd9eedc58a",
    blurb:
      "Where mountains meet the sea — Table Mountain, penguin beaches, winelands and dramatic coastal drives.",
    tags: ["Nature", "Beaches", "Wine"],
    interests: ["nature", "beaches", "food"],
    bestSeason: "Nov–Mar",
    highlights: ["Table Mountain", "Cape of Good Hope", "Boulders Beach", "V&A Waterfront"],
  },
  {
    slug: "rio-de-janeiro",
    name: "Rio de Janeiro",
    country: "Brazil",
    region: "Americas",
    photoId: "photo-1518638150340-f706e86654de",
    blurb:
      "The marvelous city — Christ the Redeemer, Copacabana's golden sands, samba rhythms and lush green peaks.",
    tags: ["Beaches", "Nature", "Nightlife"],
    interests: ["beaches", "nature", "nightlife"],
    bestSeason: "Dec–Mar",
    highlights: ["Christ the Redeemer", "Sugarloaf Mountain", "Copacabana", "Santa Teresa"],
  },
  {
    slug: "prague",
    name: "Prague",
    country: "Czech Republic",
    region: "Europe",
    photoId: "photo-1533929736458-ca588d08c8be",
    blurb:
      "A fairy-tale of spires and cobblestones — Gothic castles, baroque churches and Europe's best beer halls.",
    tags: ["History", "Architecture", "Beer"],
    interests: ["history", "architecture", "nightlife"],
    bestSeason: "May–Sep",
    highlights: ["Charles Bridge", "Prague Castle", "Old Town Square", "Astronomical Clock"],
  },
  {
    slug: "san-francisco",
    name: "San Francisco",
    country: "United States",
    region: "Americas",
    photoId: "photo-1467269204594-9661b134dd2b",
    blurb:
      "Foggy hills and bold ideas — the Golden Gate, cable cars, diverse neighborhoods and a famous food scene.",
    tags: ["City", "Food", "Tech"],
    interests: ["food", "nature", "museums"],
    bestSeason: "Sep–Nov",
    highlights: ["Golden Gate Bridge", "Alcatraz", "Fisherman's Wharf", "Mission District"],
  },
];

const FEATURED = new Set(["tokyo", "paris", "bali", "rome", "kyoto", "barcelona"]);

export function isFeatured(slug: string): boolean {
  return FEATURED.has(slug);
}

function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

/** Deterministic, realistic-looking rating (4.5–4.9) per destination. */
export function ratingFor(slug: string): number {
  return Math.round((4.5 + (hash(slug) % 5) * 0.1) * 10) / 10;
}

/** Deterministic review count, formatted like "2.4k". */
export function reviewsFor(slug: string): string {
  const n = 600 + (hash(slug + "r") % 4200);
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`;
}

export function getDestination(slug: string): Destination | undefined {
  return destinations.find((d) => d.slug === slug);
}

export function relatedDestinations(slug: string, count = 3): Destination[] {
  const current = getDestination(slug);
  if (!current) return destinations.slice(0, count);
  const sameRegion = destinations.filter((d) => d.slug !== slug && d.region === current.region);
  const others = destinations.filter((d) => d.slug !== slug && d.region !== current.region);
  return [...sameRegion, ...others].slice(0, count);
}
