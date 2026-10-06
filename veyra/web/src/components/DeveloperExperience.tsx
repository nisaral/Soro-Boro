"use client";

import { useState } from "react";
import { Check, Copy, Terminal, Play, Code2, Server, GitFork } from "lucide-react";

export default function DeveloperExperience() {
  const [activeTab, setActiveTab] = useState<"python" | "mcp" | "equiv" | "cli">("python");
  const [copied, setCopied] = useState(false);

  const snippets = {
    python: `# Python Function Integration with Veyra
from veyra import Veyra

veyra = Veyra()

@veyra.tool(
    retryable=True,
    idempotent=True,
    risk_class="low"
)
def get_customer(customer_id: int) -> dict:
    """Fetch customer record by integer ID."""
    return db.query_customer(customer_id)

# If an agent calls with string argument: get_customer(customer_id="42")
# Veyra safely normalizes "42" -> 42 without forcing an agent re-plan!
result = get_customer(customer_id="42")
print(result)`,

    mcp: `# Model Context Protocol (MCP) Middleware
from veyra.boundary import MCPToolMiddleware

middleware = MCPToolMiddleware()

# Intercepts standard JSON-RPC tools/call requests
response = middleware.handle_call_tool(
    tool_name="database_query",
    arguments=request.arguments,
    handler=my_mcp_handler,
    input_schema=tool.input_schema,
    retryable=True,
    idempotent=True
)

# Returns structured result or clean MCP error classification:
# {"isError": False, "structured_result": ...}`,

    equiv: `# Explicit Declared Equivalence (Section 7)
from veyra import Veyra

veyra = Veyra()

# Explicitly register equivalent tool endpoints
# Zero automatic semantic guessing — strict developer declaration
veyra.equivalent(
    "get_customer",
    ["crm.get_customer", "legacy.get_customer"]
)

# Hard constraints filter ensures router NEVER widens allowed action space!`,

    cli: `# Diagnostic & Benchmark CLI Commands
# 1. Audit boundary execution traces and inspect recovery metrics
$ veyra-py audit --traces runs/traces.jsonl

# 2. Run ToolMisuseBench 4-way controlled baseline evaluation
$ veyra-py toolmisuse

# Output:
# System Arm             | Success  | Recoveries  | Unsafe Retries  | Replans
# raw_agent              |   16.7% |        0.0% |               0 |       50
# veyra                  |   41.7% |       50.0% |               0 |       35`,
  };

  const copyCurrent = () => {
    navigator.clipboard.writeText(snippets[activeTab]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="py-16 sm:py-20 bg-slate-50/70 border-t border-slate-200/80">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-5 space-y-4">
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-500 bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
              Developer Experience
            </span>
            <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight">
              Drop-in boundary integration. No agent rewrite.
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
              Veyra requires zero changes to your agent reasoning prompts or conversation state. Wrap existing Python tools or insert MCP middleware at the execution boundary.
            </p>

            <div className="pt-2 space-y-2 text-xs font-mono text-slate-700">
              <div className="flex items-center gap-2 p-2 bg-white rounded border border-slate-200">
                <Terminal className="w-3.5 h-3.5 text-slate-400" />
                <span>pip install veyra</span>
              </div>
              <div className="flex items-center gap-2 p-2 bg-white rounded border border-slate-200">
                <Play className="w-3.5 h-3.5 text-emerald-600" />
                <span>veyra-py audit --traces runs/traces.jsonl</span>
              </div>
            </div>
          </div>

          <div className="lg:col-span-7">
            <div className="technical-card bg-slate-950 text-slate-100 overflow-hidden shadow-md border-slate-800">
              {/* Tabs */}
              <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/60 px-4 py-2">
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setActiveTab("python")}
                    className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                      activeTab === "python"
                        ? "bg-slate-800 text-emerald-400 font-semibold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    @veyra.tool
                  </button>
                  <button
                    onClick={() => setActiveTab("mcp")}
                    className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                      activeTab === "mcp"
                        ? "bg-slate-800 text-emerald-400 font-semibold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    MCP Middleware
                  </button>
                  <button
                    onClick={() => setActiveTab("equiv")}
                    className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                      activeTab === "equiv"
                        ? "bg-slate-800 text-emerald-400 font-semibold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Declared Equivalence
                  </button>
                  <button
                    onClick={() => setActiveTab("cli")}
                    className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                      activeTab === "cli"
                        ? "bg-slate-800 text-emerald-400 font-semibold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    CLI Audit
                  </button>
                </div>

                <button
                  onClick={copyCurrent}
                  className="flex items-center gap-1 px-2 py-1 text-xs font-mono text-slate-400 hover:text-slate-200 transition-colors"
                  title="Copy code snippet"
                >
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>

              {/* Code Container */}
              <div className="p-4 sm:p-5 font-mono text-xs overflow-x-auto leading-relaxed text-slate-300">
                <pre>{snippets[activeTab]}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
