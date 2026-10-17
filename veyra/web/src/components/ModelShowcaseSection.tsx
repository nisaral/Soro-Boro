"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Cpu,
  Zap,
  ShieldCheck,
  ExternalLink,
  Copy,
  Check,
  Sparkles,
  BarChart2,
  Database,
  ArrowRight,
  Terminal,
} from "lucide-react";

export default function ModelShowcaseSection() {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const copyText = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const models = [
    {
      id: "soro-kev-4b",
      name: "Soro-Kev-4B",
      tagline: "Flagship System-One Conformal Router",
      base: "Qwen/Qwen3-4B",
      hfUrl: "https://huggingface.co/nisaralll/soro-kev-4b",
      latency: "413 ms",
      vram: "4,048 MB (NF4)",
      accuracy: "94.50%",
      coverage: "95.00%",
      set_size: "1.07",
      color: "emerald",
      badge: "PRODUCTION & AGENT HARNESS",
      desc: "Scores user state against tool schema options in one forward prefill. NF4 quantized with SDPA attention. Zero JSON token-generation overhead and mathematically zero hallucinated tool names.",
      code: 'from soro.harness.pipeline import SoroHarness\n\n# Load in NF4 on RTX 4050 / T4 (4 GB VRAM)\nharness = SoroHarness.from_pretrained("nisaralll/soro-kev-4b")\n\ndecision = harness.route("Look up order ORD-774 and cancel its shipment")\nprint(decision.action, decision.selected_tool)',
    },
    {
      id: "soro-kev-0.8b",
      name: "Soro-Kev-0.8B",
      tagline: "Ultra-Fast Edge & On-Device Router",
      base: "Qwen/Qwen3.5-0.8B-Base",
      hfUrl: "https://huggingface.co/nisaralll/soro-kev-0.8b",
      latency: "80 ms",
      vram: "1,563 MB",
      accuracy: "89.00%",
      coverage: "95.50%",
      set_size: "1.18",
      color: "blue",
      badge: "SUB-100MS EDGE ROUTER",
      desc: "Ultra-compact System-One pointer network for local edge deployment, MCP desktop sidecars, and high-frequency routing. Sub-80ms prefill without LLM prompt generation bloat.",
      code: 'from soro.harness.pipeline import SoroHarness\n\n# 80ms edge inference on consumer laptops & edge chips\nharness = SoroHarness.from_pretrained("nisaralll/soro-kev-0.8b")\n\ndecision = harness.route("Fetch invoice PDF for client 42")\nprint(decision.action, decision.selected_tool)',
    },
    {
      id: "universal-dataset",
      name: "Universal Tool Harness",
      tagline: "26k Multi-Format Benchmark Dataset",
      base: "26,612 Records Across 6 Schema Formats",
      hfUrl: "https://huggingface.co/datasets/nisaralll/soro-universal-tool-harness",
      latency: "3 Splits",
      vram: "94 MB",
      accuracy: "6 Formats",
      coverage: "Strict Holdout",
      set_size: "Order-Invariant",
      color: "purple",
      badge: "BENCHMARK DATASET",
      desc: "Diverse dataset spanning MCP JSON-RPC, Agent Skills (SKILL.md), REST/OpenAPI, GraphQL RPC, and Python signatures. Includes 2,220 zero-shot tools and 1,200 held-out human queries.",
      code: 'from datasets import load_dataset\n\n# Load multi-format routing & argument repair rows\nds = load_dataset("nisaralll/soro-universal-tool-harness")\nprint(ds["val_zeroshot"][0])',
    },
  ];

  return (
    <section id="models" className="py-16 sm:py-24 bg-white border-t border-slate-200/80">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-12 gap-4">
          <div className="max-w-2xl space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-md bg-emerald-50 border border-emerald-200 text-xs font-mono text-emerald-800">
              <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
              <span>LIVE ON HUGGING FACE &amp; GITHUB</span>
            </div>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900">
              Trained Soro-Kev Models &amp; Dataset
            </h2>
            <p className="text-sm text-slate-600 leading-relaxed">
              Trained on Kaggle T4 GPUs and verified on RTX 4050 hardware. Soro-Kev replaces slow token generation with calibrated System-One pointer ranking.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <a
              href="https://huggingface.co/spaces/nisaralll/soro-kev-router"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 rounded-lg border border-emerald-300 shadow-xs transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
              Live Space Demo (114 Tools)
            </a>
            <a
              href="https://huggingface.co/nisaralll"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200/80 rounded-lg border border-slate-200 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Hugging Face Hub
            </a>
            <a
              href="https://github.com/nisaral/Soro-Boro"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-lg shadow-sm transition-all"
            >
              GitHub Repo
            </a>
          </div>
        </div>

        {/* 3 Model Cards */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-12">
          {models.map((model, idx) => (
            <div
              key={model.id}
              className="rounded-xl border border-slate-200 bg-slate-50/50 p-6 flex flex-col justify-between hover:border-slate-300 hover:shadow-md transition-all group"
            >
              <div>
                {/* Header row */}
                <div className="flex items-center justify-between gap-2 mb-3">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-200/80 text-slate-700 font-semibold uppercase">
                    {model.badge}
                  </span>
                  <a
                    href={model.hfUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs font-mono text-emerald-600 hover:text-emerald-700 flex items-center gap-1 group-hover:underline"
                  >
                    <span>View on Hub</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>

                <h3 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
                  <span>{model.name}</span>
                </h3>
                <p className="text-xs font-mono text-slate-500 mb-3">{model.base}</p>

                <p className="text-xs text-slate-600 leading-relaxed mb-6">
                  {model.desc}
                </p>

                {/* Metrics Table */}
                <div className="grid grid-cols-3 gap-2 p-3 bg-white border border-slate-200/80 rounded-lg text-center mb-5 shadow-xs">
                  <div>
                    <div className="text-[10px] font-mono text-slate-400 uppercase">Latency</div>
                    <div className="text-sm font-bold text-slate-900 font-mono mt-0.5">{model.latency}</div>
                  </div>
                  <div>
                    <div className="text-[10px] font-mono text-slate-400 uppercase">VRAM</div>
                    <div className="text-sm font-bold text-slate-900 font-mono mt-0.5">{model.vram}</div>
                  </div>
                  <div>
                    <div className="text-[10px] font-mono text-slate-400 uppercase">Accuracy</div>
                    <div className="text-sm font-bold text-emerald-600 font-mono mt-0.5">{model.accuracy}</div>
                  </div>
                </div>

                {/* Code Snippet Box */}
                <div className="relative rounded-lg bg-slate-900 p-3 text-[11px] font-mono text-slate-200 overflow-x-auto shadow-inner">
                  <button
                    onClick={() => copyText(model.code, idx)}
                    className="absolute top-2 right-2 p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                    title="Copy code"
                  >
                    {copiedIndex === idx ? (
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>
                  <pre className="pr-6 leading-relaxed whitespace-pre">{model.code}</pre>
                </div>
              </div>

              {/* Action Link */}
              <div className="mt-5 pt-4 border-t border-slate-200/70 flex items-center justify-between">
                <span className="text-[11px] font-mono text-slate-500">
                  {model.id === "universal-dataset" ? "26,612 records" : "from_pretrained() ready"}
                </span>
                <a
                  href={model.hfUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-900 hover:text-emerald-600 transition-colors"
                >
                  Model Card &amp; Weights <ArrowRight className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>
          ))}
        </div>

        {/* Quick Highlights Banner */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="text-xs font-mono font-semibold text-emerald-700 uppercase tracking-wider">
              Evaluated on Berkeley Function Calling &amp; Real-World Holdouts
            </div>
            <p className="text-xs text-slate-600">
              100% multiple-tool accuracy, 96.97% live-multiple accuracy, and 80ms – 413ms decision latencies.
            </p>
          </div>
          <Link
            href="/benchmarks"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-slate-900 bg-slate-100 hover:bg-slate-200 border border-slate-200 transition-colors shrink-0"
          >
            <BarChart2 className="w-3.5 h-3.5" />
            View Full Benchmark Matrix <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </section>
  );
}
