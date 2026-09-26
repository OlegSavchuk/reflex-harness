# Reflex website

The project site is a single-page overview of the Reflex coding-agent harness. It covers the repair loop, retrieval and context strategies, held-out benchmark results, and a local quickstart.

## Run locally

From this directory, run:

    npm install
    npm run dev

Open http://localhost:3000.

The quickstart commands require the credentials documented in the repository's .env.example. The benchmark panel reports the frozen Gate 8 held-out feasibility evaluation. It includes four tasks, five repeats per task and arm, and explicit sample-size and comparison caveats.

## Build

    npm run build
