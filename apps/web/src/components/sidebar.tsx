"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@aiops/ui";

/** The sidebar layout named in CLAUDE.md Section 21. */
const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/projects", label: "Projects" },
  { href: "/workflows", label: "Workflows" },
  { href: "/documents", label: "Documents" },
  { href: "/tasks", label: "Tasks" },
  { href: "/reports", label: "Reports" },
  { href: "/settings", label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Main"
      className="flex h-full w-56 shrink-0 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-800">
        <Link href="/" className="block">
          <span className="block text-sm font-semibold text-slate-900 dark:text-slate-100">
            AI Operations
          </span>
          <span className="block text-xs text-slate-500 dark:text-slate-400">
            Toolkit
          </span>
        </Link>
      </div>

      <ul className="flex-1 space-y-0.5 p-3">
        {NAV.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "block rounded-md px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-slate-100 font-medium text-slate-900 dark:bg-slate-800 dark:text-slate-100"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/60 dark:hover:text-slate-200",
                )}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>

      <div className="border-t border-slate-200 px-5 py-3 dark:border-slate-800">
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Portfolio build — all data is synthetic.
        </p>
      </div>
    </nav>
  );
}
