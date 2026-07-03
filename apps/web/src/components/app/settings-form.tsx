"use client";

import { Bell, Check, Globe, Ruler, Wallet } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";

const LANGUAGES = ["English", "Español", "Français", "Deutsch", "日本語", "العربية", "中文"];
const UNITS = ["Kilometers", "Miles"];
const CURRENCIES = ["USD ($)", "EUR (€)", "GBP (£)", "JPY (¥)", "PKR (₨)"];

interface Prefs {
  language: string;
  units: string;
  currency: string;
  emailDeals: boolean;
  tripReminders: boolean;
}

const DEFAULTS: Prefs = {
  language: "English",
  units: "Kilometers",
  currency: "USD ($)",
  emailDeals: true,
  tripReminders: true,
};

const KEY = "voyantra:prefs";

function Field({
  id,
  icon: Icon,
  label,
  children,
}: {
  id?: string;
  icon: React.ElementType;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div id={id} className="flex flex-col gap-2 scroll-mt-24 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-2">
        <Icon className="size-4 text-primary" />
        <span className="text-sm font-medium">{label}</span>
      </div>
      {children}
    </div>
  );
}

function Select({
  value,
  options,
  onChange,
}: {
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-10 rounded-lg border border-input bg-background px-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring sm:w-56"
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className={`relative h-6 w-11 rounded-full transition-colors ${on ? "bg-primary" : "bg-muted-foreground/30"}`}
    >
      <span
        className={`absolute top-0.5 size-5 rounded-full bg-white shadow transition-transform ${on ? "translate-x-5" : "translate-x-0.5"}`}
      />
    </button>
  );
}

export function SettingsForm() {
  const [prefs, setPrefs] = React.useState<Prefs>(DEFAULTS);
  const [saved, setSaved] = React.useState(false);

  React.useEffect(() => {
    try {
      const raw = window.localStorage.getItem(KEY);
      if (raw) setPrefs({ ...DEFAULTS, ...(JSON.parse(raw) as Partial<Prefs>) });
    } catch {
      /* ignore */
    }
  }, []);

  function update<K extends keyof Prefs>(key: K, value: Prefs[K]) {
    setPrefs((p) => ({ ...p, [key]: value }));
    setSaved(false);
  }

  function save() {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(prefs));
      setSaved(true);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold">Preferences</h2>
        <div className="mt-5 space-y-5">
          <Field id="language" icon={Globe} label="Language">
            <Select
              value={prefs.language}
              options={LANGUAGES}
              onChange={(v) => update("language", v)}
            />
          </Field>
          <Field icon={Ruler} label="Distance units">
            <Select value={prefs.units} options={UNITS} onChange={(v) => update("units", v)} />
          </Field>
          <Field icon={Wallet} label="Currency">
            <Select
              value={prefs.currency}
              options={CURRENCIES}
              onChange={(v) => update("currency", v)}
            />
          </Field>
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold">Notifications</h2>
        <div className="mt-5 space-y-5">
          <Field icon={Bell} label="Travel deals & inspiration">
            <Toggle on={prefs.emailDeals} onChange={(v) => update("emailDeals", v)} />
          </Field>
          <Field icon={Bell} label="Trip reminders">
            <Toggle on={prefs.tripReminders} onChange={(v) => update("tripReminders", v)} />
          </Field>
        </div>
      </section>

      <div className="flex items-center gap-3">
        <Button onClick={save} variant="gradient">
          {saved ? (
            <>
              <Check className="size-4" /> Saved
            </>
          ) : (
            "Save changes"
          )}
        </Button>
        {saved && <span className="text-sm text-muted-foreground">Your preferences are saved.</span>}
      </div>
    </div>
  );
}
