"use client";

import React, { useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Code2,
  Database,
  FileCheck,
  Flame,
  Lock,
  Play,
  RefreshCw,
  Server,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from "lucide-react";

type FaultType = "dropped_ack" | "eventual_replica" | "probe_500" | "normal";
type ScenarioType = "stripe_refund" | "github_issue";

export default function InteractiveDemo() {
  const [scenario, setScenario] = useState<ScenarioType>("stripe_refund");
  const [fault, setFault] = useState<FaultType>("dropped_ack");
  const [isRunning, setIsRunning] = useState(false);
  const [hasRun, setHasRun] = useState(false);
  const [activeTab, setActiveTab] = useState<"trace" | "wal" | "code">("trace");

  const runSimulation = () => {
    setIsRunning(true);
    setHasRun(false);
    setTimeout(() => {
      setIsRunning(false);
      setHasRun(true);
    }, 600);
  };

  return (
    <section id="demo" className="py-16 sm:py-24 bg-slate-950 text-slate-100 border-b border-slate-800">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-12 space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-xs font-mono text-amber-400">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Simulation Model (Synthetic Fault Injection)</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white flex items-center justify-center gap-3">
            <span>Execution Boundary Simulator</span>
            <span className="text-xs uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono font-normal border border-slate-700">
              Simulation
            </span>
          </h2>
          <p className="text-sm sm:text-base text-slate-400 max-w-2xl mx-auto">
            Simulated environment demonstrating execution boundary mechanics under synthetic fault injection (dropped ACKs, replica lag, probe failures).
          </p>
        </div>

        {/* Simulator Dashboard */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl">
          {/* Controls Bar */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pb-6 border-b border-slate-800">
            {/* Scenario Selector */}
            <div>
              <label className="block text-xs font-mono text-slate-400 mb-2 uppercase tracking-wider">
                1. Consequential Write
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => { setScenario("stripe_refund"); setHasRun(false); }}
                  className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium border text-left transition-all ${
                    scenario === "stripe_refund"
                      ? "bg-emerald-500/10 border-emerald-500/50 text-emerald-300"
                      : "bg-slate-800/60 border-slate-700/60 text-slate-400 hover:bg-slate-800"
                  }`}
                >
                  <div className="font-semibold">Stripe Refund</div>
                  <div className="text-[11px] opacity-70">Order #8942 ($149.99)</div>
                </button>
                <button
                  type="button"
                  onClick={() => { setScenario("github_issue"); setHasRun(false); }}
                  className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium border text-left transition-all ${
                    scenario === "github_issue"
                      ? "bg-emerald-500/10 border-emerald-500/50 text-emerald-300"
                      : "bg-slate-800/60 border-slate-700/60 text-slate-400 hover:bg-slate-800"
                  }`}
                >
                  <div className="font-semibold">GitHub Issue</div>
                  <div className="text-[11px] opacity-70">Prod Incident Ticket</div>
                </button>
              </div>
            </div>

            {/* Fault Injection Selector */}
            <div>
              <label className="block text-xs font-mono text-slate-400 mb-2 uppercase tracking-wider">
                2. Distributed Network Fault
              </label>
              <select
                value={fault}
                onChange={(e) => { setFault(e.target.value as FaultType); setHasRun(false); }}
                className="w-full bg-slate-800/90 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2.5 font-mono focus:outline-none focus:border-emerald-500"
              >
                <option value="dropped_ack">504 Timeout on committed write (Dropped ACK)</option>
                <option value="eventual_replica">Delayed visibility on eventual replica (Stale read)</option>
                <option value="probe_500">Probe 500 Outage (Reconciliation probe fails)</option>
                <option value="normal">Normal Network (200 OK)</option>
              </select>
            </div>

            {/* Action Button */}
            <div className="flex items-end">
              <button
                type="button"
                onClick={runSimulation}
                disabled={isRunning}
                className="w-full py-2.5 px-4 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold text-xs tracking-wide uppercase transition-all shadow-lg flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isRunning ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Simulating Network & Boundary...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-current" />
                    Simulate Tool Execution
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Results Comparison (Only visible after clicking or default preview) */}
          <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* LEFT: Standard Agent Framework (Naive Retries) */}
            <div className="bg-slate-950 border border-rose-900/40 rounded-xl p-5 relative overflow-hidden flex flex-col justify-between">
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-rose-900/30">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
                    <span className="font-semibold text-sm text-rose-200">Naive Agent / Raw Framework</span>
                  </div>
                  <span className="text-[11px] font-mono text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
                    Standard Retry Policy
                  </span>
                </div>

                {/* Step trace */}
                <div className="space-y-2.5 text-xs font-mono">
                  <div className="flex items-start gap-2 text-slate-400">
                    <span className="text-slate-600">0ms</span>
                    <span>1. Agent dispatches: <span className="text-slate-300">refund(order_id=&quot;8942&quot;, amount=149.99)</span></span>
                  </div>
                  {fault === "dropped_ack" && (
                    <>
                      <div className="flex items-start gap-2 text-slate-400">
                        <span className="text-slate-600">5000ms</span>
                        <span className="text-amber-400">2. Gateway 504 Timeout! Response dropped by network.</span>
                      </div>
                      <div className="flex items-start gap-2 text-slate-400">
                        <span className="text-slate-600">5100ms</span>
                        <span className="text-rose-400">3. Blind Retry triggered! Re-submitting request with new UUID...</span>
                      </div>
                      <div className="flex items-start gap-2 text-rose-300 font-bold bg-rose-950/40 p-2.5 rounded border border-rose-800/40">
                        <AlertCircle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
                        <div>
                          <div>RESULT: 2 REFUNDS CREATED ($299.98)</div>
                          <div className="text-[11px] font-normal text-rose-400 mt-0.5">
                            Customer double-refunded! Duplicate mutation committed because retry did not reuse stable logical key.
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                  {fault === "eventual_replica" && (
                    <>
                      <div className="flex items-start gap-2 text-slate-400">
                        <span className="text-slate-600">5000ms</span>
                        <span className="text-amber-400">2. Timeout. Naive probe queries read replica: returns 404 (Not Found).</span>
                      </div>
                      <div className="flex items-start gap-2 text-slate-400">
                        <span className="text-slate-600">5050ms</span>
                        <span className="text-rose-400">3. False Negative! Agent infers &quot;Write didn&apos;t happen&quot; and retries.</span>
                      </div>
                      <div className="flex items-start gap-2 text-rose-300 font-bold bg-rose-950/40 p-2.5 rounded border border-rose-800/40">
                        <AlertCircle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
                        <div>
                          <div>RESULT: DUPLICATE SIDE EFFECT</div>
                          <div className="text-[11px] font-normal text-rose-400 mt-0.5">
                            Original write committed on primary; stale replica caused premature retry.
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                  {fault === "probe_500" && (
                    <>
                      <div className="flex items-start gap-2 text-slate-400">
                        <span className="text-slate-600">5000ms</span>
                        <span className="text-amber-400">2. Timeout. Unhandled probe exception causes crash or unmanaged retry.</span>
                      </div>
                      <div className="flex items-start gap-2 text-rose-300 font-bold bg-rose-950/40 p-2.5 rounded border border-rose-800/40">
                        <AlertCircle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
                        <div>
                          <div>RESULT: UNCONTROLLED STATE DRIFT</div>
                          <div className="text-[11px] font-normal text-rose-400 mt-0.5">
                            No durable intent logged. Unclear if payment provider executed action.
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                  {fault === "normal" && (
                    <>
                      <div className="flex items-start gap-2 text-slate-400">
                        <span className="text-slate-600">240ms</span>
                        <span className="text-emerald-400">2. HTTP 200 OK received. Refund created.</span>
                      </div>
                      <div className="flex items-start gap-2 text-emerald-300 font-bold bg-emerald-950/40 p-2.5 rounded border border-emerald-800/40">
                        <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400 mt-0.5" />
                        <div>RESULT: SUCCESS ($149.99)</div>
                      </div>
                    </>
                  )}
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-rose-900/30 flex items-center justify-between text-[11px] font-mono text-rose-400">
                <span>Duplicate Risk: HIGH</span>
                <span>Audit Durability: NONE</span>
              </div>
            </div>

            {/* RIGHT: Soro-Boro Execution Boundary */}
            <div className="bg-slate-950 border border-emerald-500/40 rounded-xl p-5 relative overflow-hidden flex flex-col justify-between shadow-lg shadow-emerald-950/20">
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-emerald-500/30">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span className="font-semibold text-sm text-emerald-300">Soro-Boro Execution Boundary</span>
                  </div>
                  <span className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                    Durable Identity &amp; Reconciler
                  </span>
                </div>

                {/* Step trace */}
                <div className="space-y-2.5 text-xs font-mono">
                  <div className="flex items-start gap-2 text-slate-400">
                    <span className="text-slate-600">0ms</span>
                    <span>1. Synchronous WAL: <span className="text-emerald-400">INTENT</span> logged (<span className="text-slate-300">op_refund_8942</span>, stable key: <span className="text-slate-300">sb_key_91f4</span>)</span>
                  </div>
                  <div className="flex items-start gap-2 text-slate-400">
                    <span className="text-slate-600">12ms</span>
                    <span>2. Mutating tool dispatched with stable <span className="text-slate-300">idempotency_key</span></span>
                  </div>

                  {fault === "dropped_ack" && (
                    <>
                      <div className="flex items-start gap-2 text-slate-400">
                        <span className="text-slate-600">5000ms</span>
                        <span className="text-amber-400">3. 504 Timeout caught (UNKNOWN_ACK). Blind replay suppressed!</span>
                      </div>
                      <div className="flex items-start gap-2 text-slate-400">
                        <span className="text-slate-600">5120ms</span>
                        <span className="text-emerald-400">4. Reconciler probes Stripe with stable key: state=SUCCEEDED (ref_0042)</span>
                      </div>
                      <div className="flex items-start gap-2 text-emerald-300 font-bold bg-emerald-950/40 p-2.5 rounded border border-emerald-800/40">
                        <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400 mt-0.5" />
                        <div>
                          <div>STATUS: PREVENTED_DUPLICATE</div>
                          <div className="text-[11px] font-normal text-emerald-400 mt-0.5">
                            Reconciliation verified original refund committed. Suppressed duplicate retry. $149.99 saved!
                          </div>
                        </div>
                      </div>
                    </>
                  )}

                  {fault === "eventual_replica" && (
                    <>
                      <div className="flex items-start gap-2 text-slate-400">
                        <span className="text-slate-600">5000ms</span>
                        <span className="text-amber-400">3. 504 Timeout caught. Reconciler observes NOT_FOUND on eventual replica.</span>
                      </div>
                      <div className="flex items-start gap-2 text-slate-400">
                        <span className="text-slate-600">5060ms</span>
                        <span className="text-amber-300">4. Consistency guard: Eventual consistency cannot prove non-commit. Safe deferral enforced.</span>
                      </div>
                      <div className="flex items-start gap-2 text-amber-300 font-bold bg-amber-950/40 p-2.5 rounded border border-amber-800/40">
                        <ShieldAlert className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
                        <div>
                          <div>STATUS: AMBIGUOUS_DEFERRED</div>
                          <div className="text-[11px] font-normal text-amber-400 mt-0.5">
                            Fail-closed! Agent halted safely to prevent premature retry. Tamper-evident audit record emitted for human triage.
                          </div>
                        </div>
                      </div>
                    </>
                  )}

                  {fault === "probe_500" && (
                    <>
                      <div className="flex items-start gap-2 text-slate-400">
                        <span className="text-slate-600">5000ms</span>
                        <span className="text-amber-400">3. Timeout. Reconciler probe failed (500).</span>
                      </div>
                      <div className="flex items-start gap-2 text-amber-300 font-bold bg-amber-950/40 p-2.5 rounded border border-amber-800/40">
                        <ShieldAlert className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
                        <div>
                          <div>STATUS: AMBIGUOUS_DEFERRED (FAIL-CLOSED)</div>
                          <div className="text-[11px] font-normal text-amber-400 mt-0.5">
                            Never guess failure when reconciler is offline. Halted cleanly with cryptographic WAL record.
                          </div>
                        </div>
                      </div>
                    </>
                  )}

                  {fault === "normal" && (
                    <>
                      <div className="flex items-start gap-2 text-slate-400">
                        <span className="text-slate-600">240ms</span>
                        <span className="text-emerald-400">3. HTTP 200 OK acknowledged.</span>
                      </div>
                      <div className="flex items-start gap-2 text-emerald-300 font-bold bg-emerald-950/40 p-2.5 rounded border border-emerald-800/40">
                        <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400 mt-0.5" />
                        <div>
                          <div>STATUS: COMMITTED</div>
                          <div className="text-[11px] font-normal text-emerald-400 mt-0.5">
                            Synchronous WAL updated. Operation complete.
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-emerald-500/30 flex items-center justify-between text-[11px] font-mono text-emerald-400">
                <span>Duplicate Risk: ZERO</span>
                <span>Audit Durability: SYNCHRONOUS WAL</span>
              </div>
            </div>
          </div>

          {/* Bottom Tabs: Live WAL Inspector & Integration Code */}
          <div className="mt-8 pt-6 border-t border-slate-800">
            <div className="flex items-center gap-4 mb-4">
              <button
                type="button"
                onClick={() => setActiveTab("trace")}
                className={`text-xs font-mono px-3 py-1.5 rounded-lg border transition-all ${
                  activeTab === "trace"
                    ? "bg-emerald-500/10 border-emerald-500/50 text-emerald-300 font-semibold"
                    : "border-transparent text-slate-400 hover:text-slate-200"
                }`}
              >
                Telemetry &amp; Invariants
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("wal")}
                className={`text-xs font-mono px-3 py-1.5 rounded-lg border transition-all ${
                  activeTab === "wal"
                    ? "bg-emerald-500/10 border-emerald-500/50 text-emerald-300 font-semibold"
                    : "border-transparent text-slate-400 hover:text-slate-200"
                }`}
              >
                Write-Ahead Log (WAL JSON)
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("code")}
                className={`text-xs font-mono px-3 py-1.5 rounded-lg border transition-all ${
                  activeTab === "code"
                    ? "bg-emerald-500/10 border-emerald-500/50 text-emerald-300 font-semibold"
                    : "border-transparent text-slate-400 hover:text-slate-200"
                }`}
              >
                Python Integration Code
              </button>
            </div>

            {/* TAB CONTENT */}
            {activeTab === "trace" && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                  <div className="text-slate-500">Operation ID</div>
                  <div className="text-slate-200 font-semibold mt-1">op_refund_8942</div>
                </div>
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                  <div className="text-slate-500">Idempotency Key</div>
                  <div className="text-emerald-400 font-semibold mt-1">sb_key_91f4ae8b</div>
                </div>
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                  <div className="text-slate-500">Terminal Outcome</div>
                  <div className="text-emerald-400 font-semibold mt-1">
                    {fault === "dropped_ack" ? "PREVENTED_DUPLICATE" : fault === "eventual_replica" || fault === "probe_500" ? "AMBIGUOUS_DEFERRED" : "COMMITTED"}
                  </div>
                </div>
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                  <div className="text-slate-500">Duplicates Created</div>
                  <div className="text-emerald-400 font-bold mt-1">0 (Observed in test)</div>
                </div>
              </div>
            )}

            {activeTab === "wal" && (
              <pre className="bg-slate-950 p-4 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto leading-relaxed">
{`// 1. Synchronous INTENT flushed to disk BEFORE network dispatch
{"event_type": "INTENT", "operation_id": "op_refund_8942", "idempotency_key": "sb_key_91f4ae8b", "tool": "stripe_refund", "prev_hash": "00000000...0000", "record_hash": "7a8f9c1e2d..."}

// 2. Synchronous OUTCOME flushed upon reconciliation or completion
{"event_type": "OUTCOME", "operation_id": "op_refund_8942", "status": "${fault === "dropped_ack" ? "PREVENTED_DUPLICATE" : fault === "eventual_replica" || fault === "probe_500" ? "AMBIGUOUS_DEFERRED" : "COMMITTED"}", "provider_state": "${fault === "dropped_ack" ? "SUCCEEDED" : fault === "eventual_replica" || fault === "probe_500" ? "UNKNOWN" : "SUCCEEDED"}", "prev_hash": "7a8f9c1e2d...", "record_hash": "e4b1a8d0f3..."}`}
              </pre>
            )}

            {activeTab === "code" && (
              <pre className="bg-slate-950 p-4 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto leading-relaxed">
{`from soro_boro import soro_wrap, SideEffectClass, OperationIdentity

@soro_wrap(
    side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
    key_generator=lambda order_id, amount: f"refund_{order_id}_{amount}",
    reconciler=stripe_refund_reconciler,
    max_retries=1
)
def refund_customer(order_id: str, amount: float, op: OperationIdentity):
    return stripe.Refund.create(
        charge=order_id,
        amount=int(amount * 100),
        idempotency_key=op.idempotency_key  # Stable key passed directly
    )`}
              </pre>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
