# Soro-Boro Web Platform

Interactive visualization, architecture documentation, and synthetic failure mode simulator for **Soro-Boro: The Agent Execution Boundary**.

## Features

- **Execution Boundary Simulator**: Interactive simulation model demonstrating how Soro-Boro traps `UNKNOWN_ACK` timeouts, prevents duplicate mutations, and fails closed under replica lag or probe outages. *(Clearly labeled as a synthetic simulation model)*.
- **Architecture Deep-Dive**: Explanations of Operation Identity, Write-Ahead Logging, and atomic distributed claims.
- **Benchmarks & Oracles**: Empirical results across non-keyed services, comparing Naive Retries, SafeAgent receipt baselines, Naive Verification, and Soro-Boro.

## Getting Started

```bash
# Install dependencies
npm install

# Run local development server
npm run dev

# Run production build
npm run build
```

Open [http://localhost:3000](http://localhost:3000) with your browser.
