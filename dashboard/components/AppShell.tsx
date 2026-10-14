"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "./ThemeToggle";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const navLinks = [
    { href: "/", label: "New Session" },
    { href: "/sessions", label: "Sessions" },
    { href: "/analytics", label: "Analytics" },
  ];

  return (
    <div className="app-shell">
      <nav className="app-nav">
        <Link href="/" className="app-nav-brand">
          <div className="app-nav-brand-icon">PA</div>
          <span className="app-nav-brand-name">PayAgent</span>
        </Link>

        <div className="app-nav-links">
          {navLinks.map((link) => {
            const isActive =
              link.href === "/"
                ? pathname === "/"
                : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`app-nav-link${isActive ? " active" : ""}`}
              >
                {link.label}
              </Link>
            );
          })}
        </div>

        <div className="app-nav-actions">
          <ThemeToggle />
        </div>
      </nav>
      <main className="app-content">{children}</main>
    </div>
  );
}
