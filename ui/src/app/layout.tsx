import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "VANGUARD",
  description: "D27HQ Infrastructure & Operational Readiness Directorate console",
};

const NAV = [
  { href: "/", label: "OVERVIEW" },
  { href: "/nodes", label: "NODES" },
  { href: "/mesh", label: "MESH" },
  { href: "/services", label: "SERVICES" },
  { href: "/readiness", label: "READINESS" },
  { href: "/jobs", label: "JOBS" },
  { href: "/backups", label: "BACKUPS" },
  { href: "/audit", label: "AUDIT" },
  { href: "/logs", label: "LOGS" },
  { href: "/system-health", label: "SYSTEM HEALTH" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-[var(--background)] text-[var(--foreground)]">
        <header className="border-b border-[var(--border)] bg-[var(--surface)]">
          <div className="mx-auto flex max-w-6xl items-center gap-8 px-6 py-3">
            <div className="font-mono text-sm font-semibold tracking-widest text-neutral-200">
              VANGUARD<span className="text-neutral-600">/</span>
              <span className="font-normal text-neutral-500">D27HQ</span>
            </div>
            <nav className="flex gap-1 text-xs font-mono">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded px-3 py-1.5 tracking-wide text-neutral-400 transition-colors hover:bg-neutral-800/60 hover:text-neutral-100"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">{children}</main>
        <footer className="border-t border-[var(--border)] px-6 py-3 text-center font-mono text-[11px] text-neutral-600">
          local reference console — no cloud deployment — read-only unless noted
        </footer>
      </body>
    </html>
  );
}
