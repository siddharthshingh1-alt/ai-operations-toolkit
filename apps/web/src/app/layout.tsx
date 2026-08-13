import type { Metadata } from "next";
import { ModeBanner } from "@/components/mode-banner";
import { Sidebar } from "@/components/sidebar";
import { tryGetSystemInfo } from "@/lib/api";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Operations Toolkit",
  description:
    "AI-assisted workflows, SOPs, dashboards, trackers, and automations for B2B travel operations.",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Fetched in the layout so the mode badge is present on every single page —
  // there is no route where the active mode can be ambiguous.
  const system = await tryGetSystemInfo();

  return (
    <html lang="en">
      <body className="min-h-screen">
        <div className="flex min-h-screen">
          <Sidebar />

          <div className="flex min-w-0 flex-1 flex-col">
            <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-800 dark:bg-slate-900">
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {system?.app_name ?? "AI Operations Toolkit"}
                <span className="mx-2 text-slate-300 dark:text-slate-700">/</span>
                <span className="text-slate-400 dark:text-slate-500">
                  {system?.app_env ?? "unknown"}
                </span>
              </p>
              <ModeBanner system={system} />
            </header>

            <main className="flex-1 px-6 py-6">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
