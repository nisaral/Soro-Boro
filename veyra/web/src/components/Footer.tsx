import Link from "next/link";
import { Cpu, ShieldCheck, FileText, ExternalLink } from "lucide-react";
import GithubIcon from "./GithubIcon";

export default function Footer() {
  return (
    <footer className="border-t border-slate-200/80 bg-white py-12 text-slate-600">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-8 mb-8">
          {/* Brand Col */}
          <div className="md:col-span-2 space-y-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-600 text-white font-mono font-bold text-xs">
                SB
              </div>
              <span className="font-semibold text-slate-900 tracking-tight text-base">
                Soro-Boro
              </span>
            </div>
            <p className="text-xs text-slate-500 max-w-sm leading-relaxed">
              Execution boundary for consequential AI agent writes. Prevents unsafe retries, reuses stable operation identity, and fails closed when state is ambiguous.
            </p>
            <div className="flex items-center gap-2 pt-1 text-[11px] font-mono text-slate-400">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              soro-boro · Apache-2.0 · Python SDK
            </div>
          </div>

          {/* Core Routes */}
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">Product</h4>
            <ul className="space-y-1.5 text-xs">
              <li><Link href="/" className="hover:text-slate-900 transition-colors">Overview</Link></li>
              <li><Link href="/benchmarks" className="hover:text-slate-900 transition-colors">Benchmarks</Link></li>
              <li><Link href="/dashboard" className="hover:text-slate-900 transition-colors">Live Console</Link></li>
              <li><Link href="/architecture" className="hover:text-slate-900 transition-colors">Architecture</Link></li>
            </ul>
          </div>

          {/* Resources */}
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">Resources</h4>
            <ul className="space-y-1.5 text-xs">
              <li><Link href="/docs" className="hover:text-slate-900 transition-colors">Documentation</Link></li>
              <li><Link href="/docs#handoff" className="hover:text-slate-900 transition-colors">HandoffV1 Spec</Link></li>
              <li><Link href="/docs#kev" className="hover:text-slate-900 transition-colors">Kev Integration</Link></li>
              <li><Link href="/docs#policy" className="hover:text-slate-900 transition-colors">Policy Engine</Link></li>
            </ul>
          </div>

          {/* Open Source */}
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">Open Source</h4>
            <ul className="space-y-1.5 text-xs">
              <li><Link href="/github" className="hover:text-slate-900 transition-colors flex items-center gap-1">GitHub Repository <ExternalLink className="w-3 h-3 text-slate-400" /></Link></li>
              <li><a href="https://github.com/nisaral/EB-JEPA/blob/main/LICENSE" target="_blank" rel="noopener noreferrer" className="hover:text-slate-900 transition-colors">Apache-2.0 License</a></li>
              <li><a href="https://github.com/nisaral/EB-JEPA/blob/main/CONTRIBUTING.md" target="_blank" rel="noopener noreferrer" className="hover:text-slate-900 transition-colors">Contributing</a></li>
              <li><a href="https://github.com/nisaral/EB-JEPA/blob/main/SECURITY.md" target="_blank" rel="noopener noreferrer" className="hover:text-slate-900 transition-colors">Security Policy</a></li>
            </ul>
          </div>
        </div>

        <div className="border-t border-slate-100 pt-6 flex flex-col sm:flex-row items-center justify-between text-[11px] text-slate-400">
          <div>© {new Date().getFullYear()} Soro-Boro. Apache-2.0. Published as soro-boro.</div>
          <div className="mt-2 sm:mt-0 font-mono">
            State → Decision → Policy → Action → Observation → Verification
          </div>
        </div>
      </div>
    </footer>
  );
}
