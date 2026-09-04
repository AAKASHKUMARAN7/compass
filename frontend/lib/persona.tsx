"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { Jurisdiction } from "@/types/api";

/**
 * Who is asking.
 *
 * A switcher rather than a login screen, deliberately: the capability worth
 * showing is that the *same question returns a different answer* depending on
 * which entity governs the reader. A login form demonstrates none of that.
 *
 * Real SSO replaces the body of this provider without touching a call site --
 * every consumer only reads `persona.jurisdiction`, which is exactly what an
 * OIDC claim would supply.
 */
export interface Persona {
  id: string;
  name: string;
  role: string;
  jurisdiction: Jurisdiction;
  email: string;
}

export const PERSONAS: Persona[] = [
  {
    id: "global",
    name: "Alex Moreau",
    role: "Global Function",
    jurisdiction: "global",
    email: "alex.moreau@company.com",
  },
  {
    id: "uk",
    name: "James Whitfield",
    role: "Audit — United Kingdom",
    jurisdiction: "uk",
    email: "james.whitfield@company.co.uk",
  },
  {
    id: "india",
    name: "Priya Nair",
    role: "Advisory — India",
    jurisdiction: "india",
    email: "priya.nair@company.co.in",
  },
];

const STORAGE_KEY = "compass.persona";

interface PersonaContextValue {
  persona: Persona;
  setPersona: (id: string) => void;
}

const PersonaContext = createContext<PersonaContextValue | null>(null);

export function PersonaProvider({ children }: { children: ReactNode }) {
  const [persona, setPersonaState] = useState<Persona>(PERSONAS[0]!);

  // Restored after mount rather than during render: reading storage on the
  // server would not match the client and would trip hydration.
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      const found = PERSONAS.find((item) => item.id === stored);
      if (found) setPersonaState(found);
    } catch {
      // Private browsing or blocked storage -- the default persona is fine.
    }
  }, []);

  const setPersona = useCallback((id: string) => {
    const found = PERSONAS.find((item) => item.id === id);
    if (!found) return;
    setPersonaState(found);
    try {
      window.localStorage.setItem(STORAGE_KEY, id);
    } catch {
      // Non-fatal: the choice simply will not survive a reload.
    }
  }, []);

  const value = useMemo(() => ({ persona, setPersona }), [persona, setPersona]);

  return <PersonaContext.Provider value={value}>{children}</PersonaContext.Provider>;
}

export function usePersona(): PersonaContextValue {
  const context = useContext(PersonaContext);
  if (!context) {
    throw new Error("usePersona must be used within a PersonaProvider.");
  }
  return context;
}

export const JURISDICTION_LABELS: Record<Jurisdiction, string> = {
  global: "Global",
  uk: "United Kingdom",
  india: "India",
  us: "United States",
  singapore: "Singapore",
};

export const JURISDICTION_OPTIONS = Object.entries(JURISDICTION_LABELS) as [
  Jurisdiction,
  string,
][];
