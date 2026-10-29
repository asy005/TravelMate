import { useState, useEffect } from "react";
import { getSupportedLanguages, LanguageOption } from "@/lib/api";

const LS_KEY = "travelmate_ui_lang";

interface Props {
  value: string;
  onChange: (code: string) => void;
  className?: string;
}

export const LanguageSelector = ({ value, onChange, className = "" }: Props) => {
  const [languages, setLanguages] = useState<LanguageOption[]>([]);

  useEffect(() => {
    getSupportedLanguages()
      .then(setLanguages)
      .catch(() => {
        // Fallback minimal list if API unavailable
        setLanguages([
          { code: "en", name: "English" },
          { code: "hi", name: "Hindi" },
          { code: "kn", name: "Kannada (ಕನ್ನಡ)" },
          { code: "fr", name: "French" },
          { code: "es", name: "Spanish" },
          { code: "de", name: "German" },
          { code: "ja", name: "Japanese" },
          { code: "zh", name: "Chinese (Simplified)" },
          { code: "ar", name: "Arabic" },
          { code: "ta", name: "Tamil" },
          { code: "bn", name: "Bengali" },
        ]);
      });
  }, []);

  return (
    <select
      className={`border rounded px-2 py-1 text-sm bg-white dark:bg-gray-800 dark:text-white ${className}`}
      value={value}
      onChange={(e) => {
        onChange(e.target.value);
        localStorage.setItem(LS_KEY, e.target.value);
      }}
      aria-label="Select language"
    >
      {languages.map((l) => (
        <option key={l.code} value={l.code}>
          {l.name}
        </option>
      ))}
    </select>
  );
};

export function getStoredLanguage(): string {
  return localStorage.getItem(LS_KEY) ?? "en";
}
