"use client";

import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { BookOpen, Terminal, Code2, ShieldCheck, FileCheck, Layers, GitFork, RefreshCw, AlertOctagon } from "lucide-react";

export default function DocsPage() {
  return (
    <div className="min-h-screen flex flex-col bg-[#fcfcfc] text-slate-900">
      <Navbar />

      <main className="flex-grow py-12 sm:py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Left Docs Sidebar */}
            <aside className="lg:col-span-3 space-y-4">
              <div className="sticky top-24 technical-card p-4 bg-white">
                <div className="text-xs font-mono font-semibold text-slate-400 uppercase tracking-wider mb-3">
                  Documentation Index
                </div>
                <nav className="space-y-1 text-xs font-mono">
                  <a href="#quickstart" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-800 font-medium">1. Quickstart & Install</a>
                  <a href="#core-abstractions" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-600">2. Core Abstractions</a>
                  <a href="#python-integration" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-600">3. Python Integration</a>
                  <a href="#mcp-middleware" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-600">4. MCP Middleware</a>
                  <a href="#taxonomy" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-600">5. Failure Taxonomy</a>
                  <a href="#safety-invariants" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-600">6. Safety Invariants</a>
                  <a href="#cli-audit" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-600">7. CLI Audit & Benchmarks</a>
                </nav>
              </div>
            </aside>

            {/* Main Docs Content */}
            <div className="lg:col-span-9 space-y-10">
              {/* Section 1: Quickstart */}
              <section id="quickstart" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-emerald-600 font-semibold">
                  <Terminal className="w-4 h-4" /> Getting Started
                </div>
                <h2 className="text-2xl font-bold tracking-tight text-slate-900">
                  Quickstart & Installation
                </h2>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                  Veyra is a vendor-neutral, drop-in execution boundary layer. It sits between an agent&apos;s proposed tool call and actual tool execution.
                </p>

                <div className="space-y-3 font-mono text-xs">
                  <div className="bg-slate-950 text-slate-100 p-4 rounded-lg border border-slate-800 space-y-2">
                    <div className="text-slate-400 text-[10px] uppercase">1. Install Veyra Python Package</div>
                    <pre className="text-emerald-400"><code>pip install veyra</code></pre>
                  </div>

                  <div className="bg-slate-950 text-slate-100 p-4 rounded-lg border border-slate-800 space-y-2">
                    <div className="text-slate-400 text-[10px] uppercase">2. Audit Recorded Traces</div>
                    <pre className="text-emerald-400"><code>veyra-py audit --traces runs/traces.jsonl</code></pre>
                  </div>

                  <div className="bg-slate-950 text-slate-100 p-4 rounded-lg border border-slate-800 space-y-2">
                    <div className="text-slate-400 text-[10px] uppercase">3. Run ToolMisuseBench Controlled Baseline</div>
                    <pre className="text-emerald-400"><code>veyra-py toolmisuse</code></pre>
                  </div>
                </div>
              </section>

              {/* Section 2: Core Abstractions */}
              <section id="core-abstractions" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-500 font-semibold">
                  <Layers className="w-4 h-4 text-slate-700" /> Core Abstractions
                </div>
                <h2 className="text-xl font-bold text-slate-900">
                  ExecutableAction & ExecutionState
                </h2>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                  Veyra does not hardcode transport-specific assumptions. All tool invocations are modeled as <code>ExecutableAction</code>:
                </p>
                <div className="bg-slate-950 text-slate-100 p-4 rounded-lg font-mono text-xs border border-slate-800 leading-relaxed">
                  <pre>{`class ExecutableAction:
    tool: str
    arguments: dict
    metadata: dict  # risk_class, idempotent, retryable, permissions, equivalence_group`}</pre>
                </div>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                  The execution engine evaluates <code>ExecutionState</code> (step, history, context, caller permissions) through <code>CandidateResolver</code> and <code>RoutePolicy</code> before dispatching.
                </p>
              </section>

              {/* Section 3: Python Integration */}
              <section id="python-integration" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-500 font-semibold">
                  <Code2 className="w-4 h-4 text-slate-700" /> Python Integration
                </div>
                <h2 className="text-xl font-bold text-slate-900">
                  Python Function Decorator
                </h2>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                  Wrap any Python function using <code>@veyra.tool</code>. If an LLM proposes malformed arguments like <code>&quot;42&quot;</code> or <code>&quot;ACTIVE&quot;</code>, Veyra normalizes them cleanly:
                </p>
                <div className="bg-slate-950 text-slate-100 p-4 rounded-lg font-mono text-xs border border-slate-800 leading-relaxed">
                  <pre>{`from veyra import Veyra

veyra = Veyra()

@veyra.tool(retryable=True, idempotent=True)
def get_user(user_id: int, active: bool = True):
    return db.fetch_user(user_id)

# Raw call with string coercions executes safely without agent replan:
result = get_user(user_id="105", active="true")`}</pre>
                </div>
              </section>

              {/* Section 4: MCP Middleware */}
              <section id="mcp-middleware" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-500 font-semibold">
                  <GitFork className="w-4 h-4 text-slate-700" /> MCP Middleware
                </div>
                <h2 className="text-xl font-bold text-slate-900">
                  Model Context Protocol (MCP) Support
                </h2>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                  Drop Veyra between an existing MCP Client and MCP Server to intercept <code>tools/call</code>:
                </p>
                <div className="bg-slate-950 text-slate-100 p-4 rounded-lg font-mono text-xs border border-slate-800 leading-relaxed">
                  <pre>{`from veyra.boundary import MCPToolMiddleware

middleware = MCPToolMiddleware()

response = middleware.handle_call_tool(
    tool_name="git_push",
    arguments={"branch": "main"},
    handler=my_tool_handler,
    retryable=False,
    idempotent=False
)`}</pre>
                </div>
              </section>

              {/* Section 5: Taxonomy */}
              <section id="taxonomy" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-500 font-semibold">
                  <AlertOctagon className="w-4 h-4 text-slate-700" /> Failure Taxonomy
                </div>
                <h2 className="text-xl font-bold text-slate-900">
                  7-Tier Structured Failure Classification
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
                  <div className="p-3 bg-slate-50 rounded border border-slate-200">
                    <strong className="text-slate-900 block">SCHEMA_ERROR (400)</strong>
                    <span className="text-slate-500 text-[11px]">Type mismatches, missing args, unknown properties.</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded border border-slate-200">
                    <strong className="text-slate-900 block">TRANSIENT_ERROR (503)</strong>
                    <span className="text-slate-500 text-[11px]">502/503/504, timeouts, connection resets.</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded border border-slate-200">
                    <strong className="text-slate-900 block">RATE_LIMIT (429)</strong>
                    <span className="text-slate-500 text-[11px]">Quota exceeded, Retry-After header parsing.</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded border border-slate-200">
                    <strong className="text-slate-900 block">PRECONDITION_ERROR (404/409)</strong>
                    <span className="text-slate-500 text-[11px]">Resource not found, state locked, must be active.</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded border border-slate-200">
                    <strong className="text-slate-900 block">AUTHORIZATION_ERROR (401/403)</strong>
                    <span className="text-slate-500 text-[11px]">Permission denied, scope missing. Never retried.</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded border border-slate-200">
                    <strong className="text-slate-900 block">UNKNOWN_STATE</strong>
                    <span className="text-slate-500 text-[11px]">Write timed out unconfirmed. Zero retries.</span>
                  </div>
                </div>
              </section>

              {/* Section 6: Safety Invariants */}
              <section id="safety-invariants" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-500 font-semibold">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" /> Safety Invariants
                </div>
                <h2 className="text-xl font-bold text-slate-900">
                  Strict Safety Guarantees
                </h2>
                <ul className="space-y-2 text-xs text-slate-700 leading-relaxed list-disc list-inside">
                  <li><strong>Zero Semantic Argument Guessing</strong>: Never hallucinate missing required parameters or guess field intent.</li>
                  <li><strong>Strict Idempotency for Retries</strong>: Retries are allowed ONLY when the tool is explicitly declared <code>retryable=True</code> AND <code>idempotent=True</code>.</li>
                  <li><strong>Zero Unsafe Retries</strong>: Write mutations, financial charges, and destructive commands are strictly never retried on unknown-state timeouts.</li>
                  <li><strong>Action Space Invariant</strong>: A routing or candidate resolution component must never widen the policy-allowed action space.</li>
                </ul>
              </section>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
