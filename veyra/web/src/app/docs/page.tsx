"use client";

import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { BookOpen, Terminal, Code2, ShieldCheck, FileCheck, Layers, GitFork, RefreshCw, AlertOctagon, Cpu, CheckCircle2 } from "lucide-react";

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
                  Soro v0.2.0 docs
                </div>
                <nav className="space-y-1 text-xs font-mono">
                  <a href="#quickstart" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-800 font-medium">1. Quickstart & Install</a>
                  <a href="#public-api" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-600">2. Unified Public API</a>
                  <a href="#frameworks" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-600">3. Framework Integrations</a>
                  <a href="#mcp-interceptor" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-600">4. MCP client interceptor</a>
                  <a href="#config-system" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-600">5. Configuration System</a>
                  <a href="#replay-diff" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-600">6. Replay & Trajectory Diffing</a>
                  <a href="#unknown-ack" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-600">7. UNKNOWN_ACK & Transactions</a>
                  <a href="#plugins" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-600">8. Plugin Architecture</a>
                  <a href="#cli-reference" className="block py-1.5 px-2 rounded hover:bg-slate-100 text-slate-600">9. CLI Reference</a>
                </nav>
              </div>
            </aside>

            {/* Main Docs Content */}
            <div className="lg:col-span-9 space-y-10">
              {/* Section 1: Quickstart */}
              <section id="quickstart" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-emerald-600 font-semibold">
                  <Terminal className="w-4 h-4" /> 1. Getting Started
                </div>
                <h2 className="text-2xl font-bold tracking-tight text-slate-900">
                  Quickstart & Installation
                </h2>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                  Soro is an agent framework at the tool boundary: register tools, route without an LLM, wrap execution, abstain when unsure.
                </p>

                <div className="space-y-3 font-mono text-xs">
                  <div className="bg-slate-950 text-slate-100 p-4 rounded-lg border border-slate-800 space-y-2">
                    <div className="text-slate-400 text-[10px] uppercase">Install</div>
                    <pre className="text-emerald-400"><code>pip install -e ./python[dev]</code></pre>
                  </div>

                  <div className="bg-slate-950 text-slate-100 p-4 rounded-lg border border-slate-800 space-y-2">
                    <div className="text-slate-400 text-[10px] uppercase">Import</div>
                    <pre className="text-emerald-400"><code>from soro import Soro, SideEffectClass</code></pre>
                  </div>
                </div>
              </section>

              {/* Section 2: Public API */}
              <section id="public-api" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-500 font-semibold">
                  <Code2 className="w-4 h-4 text-slate-700" /> 2. Unified Public API &amp; Harness
                </div>
                <h2 className="text-xl font-bold text-slate-900">
                  One entry point (`from soro.harness.pipeline import SoroHarness`)
                </h2>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                  Load pretrained Hugging Face models (`nisaralll/soro-kev-4b` or `0.8b`), route queries, auto-repair arguments, and guard execution:
                </p>
                <div className="bg-slate-950 text-slate-100 p-4 rounded-lg font-mono text-xs border border-slate-800 leading-relaxed">
                  <pre>{`from soro.harness.pipeline import SoroHarness

# Load pretrained System-One pointer router from Hugging Face
harness = SoroHarness.from_pretrained("nisaralll/soro-kev-4b")

@harness.tool(description="Process customer refund", side_effect="mutation")
def process_refund(order_id: str, amount: float) -> dict:
    return {"status": "ok", "order_id": order_id, "amount": amount}

# Single-prefill conformal routing in ~413ms (NF4)
decision = harness.route("Please refund $99.00 for order ORD-102")
print("Action:", decision.action)          # "EXECUTE"
print("Tool:", decision.selected_tool)     # "process_refund"

# Execute with auto argument repair & loop-guard
outcome = harness.execute("process_refund", {"orderId": "ORD-102", "amount": "99.00"})
print("Outcome:", outcome.data)`}</pre>
                </div>
              </section>

              {/* Section 3: Framework Integrations */}
              <section id="frameworks" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-500 font-semibold">
                  <Cpu className="w-4 h-4 text-slate-700" /> 3. Framework Integrations
                </div>
                <h2 className="text-xl font-bold text-slate-900">
                  First-Party Framework Adapters
                </h2>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                  Soro-Boro integrates seamlessly into major AI agent orchestration frameworks without modifying their graph or agent runtime:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                  <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-2">
                    <h3 className="font-mono font-semibold text-xs text-slate-900">OpenAI Agents SDK</h3>
                    <pre className="text-[11px] font-mono text-slate-700 bg-white p-2.5 rounded border border-slate-200">{`from soro_boro import soro_wrap
# Wrap tools directly before passing to Agent
agent_tools = [soro_wrap(...)(my_tool)]`}</pre>
                  </div>

                  <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-2">
                    <h3 className="font-mono font-semibold text-xs text-slate-900">LangGraph</h3>
                    <pre className="text-[11px] font-mono text-slate-700 bg-white p-2.5 rounded border border-slate-200">{`from soro_boro import soro_wrap

wrapped_tool = soro_wrap(...)(my_mutating_node)
graph.add_node("safe_writer", wrapped_tool)`}</pre>
                  </div>

                  <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-2">
                    <h3 className="font-mono font-semibold text-xs text-slate-900">AutoGen</h3>
                    <pre className="text-[11px] font-mono text-slate-700 bg-white p-2.5 rounded border border-slate-200">{`from soro_boro import soro_wrap

user_proxy.register_function(
    function_map={"charge": soro_wrap(...)(charge_fn)}
)`}</pre>
                  </div>

                  <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-2">
                    <h3 className="font-mono font-semibold text-xs text-slate-900">LlamaIndex / CrewAI</h3>
                    <pre className="text-[11px] font-mono text-slate-700 bg-white p-2.5 rounded border border-slate-200">{`from soro_boro import soro_wrap

safe_fn = soro_wrap(...)(crew_tool_fn)`}</pre>
                  </div>
                </div>
              </section>

              <section id="mcp-interceptor" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-500 font-semibold">
                  <Layers className="w-4 h-4 text-slate-700" /> 4. MCP client interceptor
                </div>
                <h2 className="text-xl font-bold text-slate-900">
                  Wrap MCP tool calls in-process
                </h2>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                  Soro-Boro is not an external network proxy. Wrap the MCP client or individual tools so proposals pass through the execution contract before the server runs.
                </p>
                <div className="bg-slate-950 text-slate-100 p-4 rounded-lg font-mono text-xs border border-slate-800 leading-relaxed">
                  <pre>{`# Agent proposes -> soro_wrap(mcp_tool) -> MCP server
# CLI: soro-boro audit --wal runs/soro_boro_wal.jsonl`}</pre>
                </div>
              </section>

              {/* Section 5: Configuration System */}
              <section id="config-system" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-500 font-semibold">
                  <FileCheck className="w-4 h-4 text-slate-700" /> 5. Configuration System
                </div>
                <h2 className="text-xl font-bold text-slate-900">
                  Human-Readable `soro_boro.yaml` Config
                </h2>
                <div className="bg-slate-950 text-slate-100 p-4 rounded-lg font-mono text-xs border border-slate-800 leading-relaxed">
                  <pre>{`soro_boro:
  mode: fail_closed
  wal_path: "runs/soro_boro_wal.jsonl"

policy:
  tenant_isolation: true
  authorization: true
  freshness: true
  consistency_guards: true

recovery:
  unknown_ack: reconcile_or_defer
  retries:
    enabled: true
    max_attempts: 1`}</pre>
                </div>
                <div className="flex gap-4 font-mono text-xs pt-2">
                  <div className="p-3 bg-slate-100 rounded border border-slate-200 flex-1">
                    <span className="font-semibold text-slate-900">$ soro-boro config validate</span>
                    <p className="text-slate-600 text-[11px] pt-1">Validates mode, constraints, and retry limits.</p>
                  </div>
                  <div className="p-3 bg-slate-100 rounded border border-slate-200 flex-1">
                    <span className="font-semibold text-slate-900">$ soro-boro config explain</span>
                    <p className="text-slate-600 text-[11px] pt-1">Explains active policies and runtime rules.</p>
                  </div>
                </div>
              </section>

              {/* Section 6: Replay & Trajectory Diffing */}
              <section id="replay-diff" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-500 font-semibold">
                  <RefreshCw className="w-4 h-4 text-slate-700" /> 6. Replay & Trajectory Diffing
                </div>
                <h2 className="text-xl font-bold text-slate-900">
                  Dry-Run Trajectory Reconstruction
                </h2>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                  Reconstruct trajectory decisions without performing side effects by default (DRY_RUN mode):
                </p>
                <div className="bg-slate-950 text-slate-100 p-4 rounded-lg font-mono text-xs border border-slate-800 leading-relaxed">
                  <pre>{`# Dry-run replay of a trace JSON
$ soro-boro replay run.json

# Opt-in to live execution
$ soro-boro replay run.json --execute

# Compare step-by-step diffs between two runs
$ soro-boro diff run1.json run2.json`}</pre>
                </div>
              </section>

              {/* Section 7: UNKNOWN_ACK */}
              <section id="unknown-ack" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-500 font-semibold">
                  <ShieldCheck className="w-4 h-4 text-slate-700" /> 7. UNKNOWN_ACK & Transaction Engine
                </div>
                <h2 className="text-xl font-bold text-slate-900">
                  First-Class Non-Idempotent Mutation Protection
                </h2>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                  When network drops occur during non-idempotent mutations, Soro-Boro classifies the outcome as <code>UNKNOWN_ACK</code>. Rather than blindly replaying the request (which risks duplicate charging or state corruption), Soro-Boro enforces reconciliation before replay or defers execution safely.
                </p>
              </section>

              {/* Section 8: Plugins */}
              <section id="plugins" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-500 font-semibold">
                  <GitFork className="w-4 h-4 text-slate-700" /> 8. Plugin Architecture
                </div>
                <h2 className="text-xl font-bold text-slate-900">
                  `@soro_boro_plugin` Decorator & Metadata Registry
                </h2>
                <div className="bg-slate-950 text-slate-100 p-4 rounded-lg font-mono text-xs border border-slate-800 leading-relaxed">
                  <pre>{`from soro_boro.plugins import soro_boro_plugin

@soro_boro_plugin(name="stripe_policy", version="1.0.0", capabilities=["payment_safety"])
class StripePolicyPack:
    ...`}</pre>
                </div>
              </section>

              {/* Section 9: CLI Reference */}
              <section id="cli-reference" className="technical-card p-6 sm:p-8 bg-white space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-500 font-semibold">
                  <Terminal className="w-4 h-4 text-slate-700" /> 9. CLI Command Reference
                </div>
                <div className="border border-slate-200 rounded-lg overflow-hidden text-xs font-mono">
                  <table className="w-full text-left">
                    <thead className="bg-slate-100 border-b border-slate-200 font-semibold text-slate-700">
                      <tr>
                        <th className="p-2.5">Command</th>
                        <th className="p-2.5">Description</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      <tr><td className="p-2.5 text-emerald-600 font-bold">soro-boro doctor</td><td className="p-2.5">Check Python environment and dependency readiness</td></tr>
                      <tr><td className="p-2.5 text-slate-900 font-medium">soro-boro init</td><td className="p-2.5">Initialize a default `soro_boro.yaml` config file</td></tr>
                      <tr><td className="p-2.5 text-slate-900 font-medium">soro-boro config validate</td><td className="p-2.5">Validate syntax and constraints of configuration</td></tr>
                      <tr><td className="p-2.5 text-slate-900 font-medium">soro-boro config explain</td><td className="p-2.5">Print human-readable breakdown of active policies</td></tr>
                      <tr><td className="p-2.5 text-slate-900 font-medium">soro-boro inspect tool &lt;name&gt;</td><td className="p-2.5">Inspect tool schema, parameters, and risk level</td></tr>
                      <tr><td className="p-2.5 text-slate-900 font-medium">soro-boro audit --wal &lt;file&gt;</td><td className="p-2.5">Audit Write-Ahead Log records and verify hash chain</td></tr>
                      <tr><td className="p-2.5 text-slate-900 font-medium">soro-boro replay &lt;file&gt;</td><td className="p-2.5">Replay execution trajectory trace in DRY_RUN mode</td></tr>
                      <tr><td className="p-2.5 text-slate-900 font-medium">soro-boro diff &lt;run1&gt; &lt;run2&gt;</td><td className="p-2.5">Diff tool selection, outcomes, and latencies between runs</td></tr>
                      <tr><td className="p-2.5 text-slate-900 font-medium">soro-boro bench run &lt;suite&gt;</td><td className="p-2.5">Execute reproducible benchmarks (e.g. undobench, mcpmark)</td></tr>
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
