import Link from "next/link";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import HeroExecutionVisual from "@/components/HeroExecutionVisual";
import InteractiveDemo from "@/components/InteractiveDemo";
import ModelShowcaseSection from "@/components/ModelShowcaseSection";
import ExecutionComparison from "@/components/ExecutionComparison";
import CoreCapabilities from "@/components/CoreCapabilities";
import DeveloperExperience from "@/components/DeveloperExperience";
import RoadmapSection from "@/components/RoadmapSection";
import GithubIcon from "@/components/GithubIcon";
import { BookOpen, Sparkles, BarChart3, Terminal, Cpu } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col bg-[#fcfcfc] text-slate-900">
      <Navbar />

      <main className="flex-grow">
        {/* HERO SECTION */}
        <section className="relative pt-12 sm:pt-16 pb-16 sm:pb-20 technical-grid-bg border-b border-slate-200/80">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto space-y-4 mb-10">
              {/* Badge */}
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 border border-slate-200/80 text-xs font-mono text-slate-700">
                <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span className="font-semibold text-emerald-800">Soro-Kev 4B &amp; 0.8B Models Live</span>
                <span className="text-slate-400">|</span>
                <span className="text-slate-600">Conformal System-One Tool Routing &amp; Execution Boundary</span>
              </div>

              {/* Main Headline */}
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-slate-900 leading-[1.1]">
                System-One tool routing. <br className="hidden sm:inline" />
                Zero blind retries. <br className="hidden sm:inline" />
                Zero hallucinated tools.
              </h1>

              {/* Tagline & Subtitle */}
              <p className="text-base sm:text-lg text-slate-600 leading-relaxed max-w-2xl mx-auto">
                Soro combines sub-100ms conformal pointer routing with deterministic execution guards. Route 50+ tool schemas in a single prefill pass without token-by-token JSON generation.
              </p>

              {/* Primary & Secondary CTAs */}
              <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
                <a
                  href="#models"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 shadow-md transition-all cursor-pointer"
                >
                  <Cpu className="w-4 h-4 text-white" />
                  Explore Models &amp; Weights
                </a>
                <a
                  href="#demo"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium text-slate-900 bg-white hover:bg-slate-50 border border-slate-300 shadow-xs transition-all cursor-pointer"
                >
                  <Sparkles className="w-4 h-4 text-emerald-500" />
                  Interactive Simulator
                </a>
                <Link
                  href="/dashboard"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium text-slate-800 bg-white hover:bg-slate-50 border border-slate-200 shadow-sm transition-all"
                >
                  <Terminal className="w-4 h-4 text-slate-500" />
                  Live Console
                </Link>
                <Link
                  href="/benchmarks"
                  className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
                >
                  <BarChart3 className="w-4 h-4" />
                  Benchmarks
                </Link>
                <Link
                  href="/github"
                  className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
                >
                  <GithubIcon className="w-4 h-4" />
                  GitHub
                </Link>
              </div>
            </div>

            {/* HERO VISUAL CONTAINER */}
            <HeroExecutionVisual />
          </div>
        </section>

        {/* INTERACTIVE FAILURE MODE SIMULATOR */}
        <InteractiveDemo />

        {/* TRAINED SORO-KEV MODELS & HUGGING FACE RELEASES */}
        <ModelShowcaseSection />

        {/* WHY: EXECUTION COMPARISON */}
        <ExecutionComparison />

        {/* HOW: CORE CAPABILITIES */}
        <CoreCapabilities />

        {/* DEVELOPER EXPERIENCE & CODE */}
        <DeveloperExperience />

        {/* ROADMAP */}
        <RoadmapSection />

        {/* FINAL GITHUB CTA SECTION */}
        <section className="py-16 sm:py-20 bg-slate-900 text-white">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center space-y-6">
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
              Build with Soro.
            </h2>
            <p className="text-slate-400 max-w-xl mx-auto text-sm sm:text-base leading-relaxed">
              Open-source tool-boundary reliability middleware for Python functions and MCP tool servers.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
              <Link
                href="/github"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-semibold text-slate-900 bg-white hover:bg-slate-100 shadow-md transition-all"
              >
                <GithubIcon className="w-4 h-4" />
                GitHub Repository
              </Link>
              <Link
                href="/docs"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-medium text-slate-300 hover:text-white border border-slate-700 hover:bg-slate-800 transition-all"
              >
                <BookOpen className="w-4 h-4" />
                Documentation
              </Link>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
