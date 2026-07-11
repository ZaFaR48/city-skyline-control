import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { activateAccount } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Role } from "@/lib/types";

export const Route = createFileRoute("/activate")({ component: ActivatePage });
function ActivatePage() {
  const navigate = useNavigate();
  const { language, setLanguage, role: roleLabel, t } = useI18n();
  const initialCode =
    typeof window !== "undefined"
      ? (new URLSearchParams(window.location.search).get("code") ?? "")
      : "";
  const [code, setCode] = useState(initialCode);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ username: string; role: Role; is_active: boolean } | null>(
    null,
  );
  const [copied, setCopied] = useState(false);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError(t("activate.mismatch"));
      return;
    }
    try {
      const activated = await activateAccount(code, password);
      setResult(activated);
    } catch {
      setError(t("activate.failed"));
    }
  }
  return (
    <div className="min-h-screen grid place-items-center p-4">
      <form onSubmit={submit} className="glass rounded-xl p-7 w-full max-w-md space-y-4">
        <div className="flex justify-end">
          <select
            aria-label="Language"
            value={language}
            onChange={(event) => setLanguage(event.target.value as "ru" | "tj" | "en")}
            className="h-8 rounded bg-input border border-border px-2 text-xs"
          >
            <option value="ru">RU</option>
            <option value="tj">TJ</option>
            <option value="en">EN</option>
          </select>
        </div>
        <ShieldCheck className="size-8 text-primary" />
        <h1 className="text-xl font-semibold">{t("activate.title")}</h1>
        {result ? (
          <>
            <p className="text-sm text-success">{t("activate.success")}</p>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-xs text-muted-foreground">{t("activate.username")}</dt>
                <dd className="font-mono">{result.username}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">{t("activate.role")}</dt>
                <dd>{roleLabel(result.role)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">{t("activate.status")}</dt>
                <dd>{result.is_active ? t("common.active") : t("common.inactive")}</dd>
              </div>
            </dl>
            <button
              type="button"
              onClick={async () => {
                await navigator.clipboard.writeText(result.username);
                setCopied(true);
              }}
              className="h-10 px-4 border border-border rounded"
            >
              {copied ? t("activate.copied") : t("activate.copy")}
            </button>
            <button
              type="button"
              onClick={() => navigate({ to: "/login" })}
              className="h-10 px-4 bg-primary text-primary-foreground rounded"
            >
              {t("activate.login")}
            </button>
          </>
        ) : (
          <>
            <label className="block text-xs">
              {t("activate.code")}
              <input
                required
                value={code}
                onChange={(event) => setCode(event.target.value)}
                className="mt-1 w-full h-10 px-3 bg-input border border-border rounded"
              />
            </label>
            <label className="block text-xs">
              {t("activate.password")}
              <input
                required
                minLength={12}
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-1 w-full h-10 px-3 bg-input border border-border rounded"
              />
            </label>
            <label className="block text-xs">
              {t("activate.confirm")}
              <input
                required
                minLength={12}
                type="password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                className="mt-1 w-full h-10 px-3 bg-input border border-border rounded"
              />
            </label>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <button className="w-full h-10 bg-primary text-primary-foreground rounded">
              {t("activate.submit")}
            </button>
          </>
        )}
      </form>
    </div>
  );
}
