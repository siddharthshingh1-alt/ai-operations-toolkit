import { Badge, Card, CardHeader } from "@aiops/ui";
import { tryGetSystemInfo } from "@/lib/api";

export const metadata = { title: "Settings — AI Operations Toolkit" };

export default async function SettingsPage() {
  const system = await tryGetSystemInfo();

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Settings
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Configuration is read from environment variables. This page shows the
          current values; it does not edit them.
        </p>
      </header>

      <Card>
        <CardHeader
          title="AI mode"
          description="How AI calls are handled right now."
          action={
            system ? (
              <Badge tone={system.demo_mode ? "success" : "info"}>
                {system.demo_mode ? "Demo Mode" : "Live"}
              </Badge>
            ) : null
          }
        />
        <div className="space-y-3 px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
          {system?.demo_mode ? (
            <>
              <p>
                AI calls replay previously recorded real outputs. No API key is
                needed and nothing is charged.
              </p>
              <p>
                {system.demo_recordings > 0
                  ? `${system.demo_recordings} recording${system.demo_recordings === 1 ? "" : "s"} available.`
                  : "No recordings exist yet, so AI actions will report that rather than inventing an answer."}
              </p>
              <p>
                To run AI live instead, set{" "}
                <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
                  DEMO_MODE=false
                </code>{" "}
                and supply an API key in{" "}
                <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
                  .env
                </code>
                .
              </p>
            </>
          ) : (
            <p>
              AI calls go live to <strong>{system?.ai_provider}</strong> and are
              billed to the configured account.
            </p>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Integrations"
          description="Email, calendar, and booking data sources."
        />
        <div className="space-y-2 px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
          <p>
            All integrations run against synthetic datasets. Nothing connects to
            a real mailbox, calendar, airline, or payment system.
          </p>
          <p>
            Real OAuth integrations are a documented future improvement, not a
            v1 feature — the configuration layer rejects any value other than{" "}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
              mock
            </code>
            .
          </p>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Cost tracking"
          description="Models with a known price, used to estimate spend per AI call."
        />
        <div className="px-5 py-4">
          {system && system.priced_models.length > 0 ? (
            <ul className="flex flex-wrap gap-2">
              {system.priced_models.map((model) => (
                <li key={model}>
                  <Badge>{model}</Badge>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              No pricing data loaded.
            </p>
          )}
          <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
            A call on a model that is not listed records its token counts but
            reports no cost, rather than showing a guessed figure.
          </p>
        </div>
      </Card>
    </div>
  );
}
