"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Cpu, BookOpen, BarChart3, Layers, Terminal, Sparkles } from "lucide-react";
import GithubIcon from "./GithubIcon";

export default function Navbar() {
  const pathname = usePathname();

  const navLinks = [
    { href: "/", label: "Overview", icon: Cpu },
    { href: "/benchmarks", label: "Benchmarks", icon: BarChart3 },
    { href: "/dashboard", label: "Live Console", icon: Terminal },
    { href: "/architecture", label: "Architecture", icon: Layers },
    { href: "/docs", label: "Docs", icon: BookOpen },
    { href: "/github", label: "GitHub", icon: GithubIcon },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8 h-16">
        {/* Brand Logo & Title */}
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-white font-mono font-bold text-sm shadow-sm group-hover:bg-slate-800 transition-colors">
              V
            </div>
            <div className="flex flex-col">
              <span className="font-semibold text-slate-900 tracking-tight text-base group-hover:text-slate-700 transition-colors">
                Veyra
              </span>
            </div>
          </Link>
          <span className="hidden sm:inline-block px-2 py-0.5 rounded border border-slate-200 bg-slate-50 text-[11px] font-mono text-slate-600">
            v0.1.0-alpha · Apache-2.0
          </span>
        </div>

        {/* Desktop Navigation Links */}
        <nav className="hidden md:flex items-center gap-1">
          {navLinks.map((link) => {
            const Icon = link.icon;
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? "bg-slate-100 text-slate-900 font-semibold"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? "text-slate-900" : "text-slate-400"}`} />
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Right Action CTAs */}
        <div className="flex items-center gap-2">
          <Link
            href="/docs"
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200/80 rounded-md border border-slate-200/80 transition-colors"
          >
            Docs
          </Link>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md shadow-sm transition-all"
          >
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            Get Started
          </Link>
        </div>
      </div>

      {/* Mobile Bar */}
      <div className="flex md:hidden border-t border-slate-100 px-3 py-1.5 gap-1 overflow-x-auto">
        {navLinks.map((link) => {
          const isActive = pathname === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`whitespace-nowrap px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                isActive ? "bg-slate-900 text-white" : "text-slate-600 bg-slate-100"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </div>
    </header>
  );
}
