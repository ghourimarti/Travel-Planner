import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({ baseDirectory: __dirname });

const eslintConfig = [
  ...compat.extends("next/core-web-vitals"),
  {
    ignores: [".next/**", "node_modules/**", "coverage/**"],
  },
  {
    rules: {
      "react/no-unescaped-entities": "off",
      // We use plain <img> with the Unsplash CDN (no next/image optimizer / sharp dep).
      "@next/next/no-img-element": "off",
    },
  },
];

export default eslintConfig;
