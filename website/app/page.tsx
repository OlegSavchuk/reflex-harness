"use client";

import React from "react";

const GITHUB = "https://github.com/OlegSavchuk/reflex-harness";
const SHORT = "https://www.youtube.com/shorts/aIvHf8vsWBM";

const sections = [
  { id: "introduction", label: "Introduction" },
  { id: "features", label: "Features" },
  { id: "compare", label: "Compare" },
  { id: "benchmarks", label: "Benchmarks" },
  { id: "hands", label: "Hands" },
  { id: "cookbook", label: "Cookbook" },
  { id: "ship-it", label: "Ship it" },
];

const gate8Arms = [
  { name: "Plain retry", tag: "BASELINE", total: 0, oscillation: 0, repetition: 0, cost: "$0.0647", perFix: "—", style: "plain" },
  { name: "Fixed fallback", tag: "FIXED ORDER", total: 4, oscillation: 4, repetition: 0, cost: "$0.0391", perFix: "$0.0098", style: "fallback" },
  { name: "Reflex + memory", tag: "MEMORY GUIDED", total: 13, oscillation: 5, repetition: 8, cost: "$0.0366", perFix: "$0.0028", style: "memory" },
];

function SectionHeading({ number, eyebrow, title, detail, compactMeta = false }: { number: string; eyebrow: string; title: string; detail?: string; compactMeta?: boolean }) {
  return (
    <div className="section-heading">
      <div className={"section-heading-meta" + (compactMeta ? " section-heading-meta-compact" : "")}><span>{number} / 07</span><i />{eyebrow}</div>
      <h2>{title}</h2>
      {detail && <p>{detail}</p>}
    </div>
  );
}

function FlowIcon({ kind }: { kind: number }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const drawings = [
    <><path d="M4 7h5m6 0h5M4 17h3m6 0h7M9 5v4m4 6v4"/><circle cx="12" cy="7" r="2"/><circle cx="9" cy="17" r="2"/></>,
    <><rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m12 0h4M2 15h4m12 0h4M10 10l4 4m0-4-4 4"/></>,
    <><rect x="4" y="4" width="16" height="16" rx="3"/><path d="m8 12 2.5 2.5L16 9"/></>,
    <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.7 9A7 7 0 0 1 18 6.5L20 12M4 12l2 5.5A7 7 0 0 0 18.3 15"/></>,
    <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></>,
  ];
  return <svg className="flow-icon-svg" viewBox="0 0 24 24" aria-hidden="true" {...common}>{drawings[kind]}</svg>;
}

function GlyphAgent() {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    const width = 460;
    const height = 570;
    const mask = document.createElement("canvas");
    mask.width = width;
    mask.height = height;
    const maskContext = mask.getContext("2d", { willReadFrequently: true });
    if (!maskContext) return;

    // A hooded, abstract agent silhouette keeps the character art original to Reflex.
    maskContext.fillStyle = "#fff";
    maskContext.beginPath();
    maskContext.moveTo(230, 22);
    maskContext.bezierCurveTo(139, 22, 105, 92, 112, 171);
    maskContext.bezierCurveTo(117, 215, 100, 242, 72, 271);
    maskContext.bezierCurveTo(34, 311, 18, 384, 20, 548);
    maskContext.bezierCurveTo(91, 544, 137, 522, 170, 488);
    maskContext.bezierCurveTo(187, 510, 207, 521, 230, 521);
    maskContext.bezierCurveTo(253, 521, 273, 510, 290, 488);
    maskContext.bezierCurveTo(323, 522, 369, 544, 440, 548);
    maskContext.bezierCurveTo(442, 384, 426, 311, 388, 271);
    maskContext.bezierCurveTo(360, 242, 343, 215, 348, 171);
    maskContext.bezierCurveTo(355, 92, 321, 22, 230, 22);
    maskContext.closePath();
    maskContext.fill();

    const pixels = maskContext.getImageData(0, 0, width, height).data;
    const cells: Array<{ x: number; y: number; char: string; tone: number; size: number }> = [];
    const glyphs = "@#%&B8XMW$*+!?/\\<>[]{}=~:;";
    for (let y = 24; y < height - 8; y += 13) {
      for (let x = 8; x < width - 8; x += 10) {
        const alpha = pixels[(y * width + x) * 4 + 3];
        if (alpha < 100) continue;
        const edge = y < 95 || y > 440 || x < 63 || x > 397;
        if (!edge && ((x * 7 + y * 13) % 11 === 0)) continue;
        const pick = (x * 17 + y * 31 + (x * y) % 23) % glyphs.length;
        cells.push({ x, y, char: glyphs[pick], tone: (x + y * 3) % 7, size: (x + y) % 5 === 0 ? 12 : 11 });
      }
    }

    const draw = () => {
      const rect = canvas.getBoundingClientRect();
      if (!rect.width) return;
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(rect.width * ratio);
      canvas.height = Math.round(rect.width * height / width * ratio);
      const scale = rect.width / width;
      context.setTransform(ratio * scale, 0, 0, ratio * scale, 0, 0);
      context.clearRect(0, 0, width, height);

      // Fine orbital rings give the shifting symbols a quiet recursive frame.
      context.save();
      context.strokeStyle = "rgba(224, 239, 252, .19)";
      context.lineWidth = 1;
      context.setLineDash([2, 8]);
      context.beginPath();
      context.ellipse(230, 280, 207, 247, 0, 0, Math.PI * 2);
      context.stroke();
      context.restore();

      for (const cell of cells) {
        context.font = `${cell.size}px ui-monospace, SFMono-Regular, Menlo, monospace`;
        context.fillStyle = cell.tone === 0 || cell.tone === 3 ? "#ffe2c6" : "#f4bd91";
        context.globalAlpha = cell.tone === 2 ? 0.62 : 0.94;
        context.fillText(cell.char, cell.x, cell.y);
      }
      context.globalAlpha = 1;

      // A quiet faceplate makes the character read as an agent rather than a texture.
      context.strokeStyle = "rgba(231, 243, 255, .42)";
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(145, 171);
      context.quadraticCurveTo(230, 126, 315, 171);
      context.quadraticCurveTo(320, 205, 289, 221);
      context.quadraticCurveTo(230, 244, 171, 221);
      context.quadraticCurveTo(140, 205, 145, 171);
      context.stroke();
      context.fillStyle = "#e8f4ff";
      context.font = "12px ui-monospace, SFMono-Regular, Menlo, monospace";
      context.fillText("<  o   o  >", 181, 188);
      context.fillStyle = "#f4bd91";
      context.fillText("/  REFLEX  \\", 181, 210);
    };

    draw();
    const resizeObserver = new ResizeObserver(draw);
    resizeObserver.observe(canvas);
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let timer: number | undefined;
    if (!reduceMotion.matches) {
      timer = window.setInterval(() => {
        // Change only a small group each beat, like characters refreshing in a live terminal.
        for (let i = 0; i < 28; i++) {
          const index = Math.floor(Math.random() * cells.length);
          const cell = cells[index];
          if (cell) cell.char = glyphs[Math.floor(Math.random() * glyphs.length)];
        }
        draw();
      }, 280);
    }
    return () => {
      resizeObserver.disconnect();
      if (timer) window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="glyph-art" aria-label="A shifting character illustration of the Reflex agent">
      <canvas ref={canvasRef} role="img" aria-label="Hooded agent portrait built from changing terminal symbols" />
      <div className="glyph-art-label"><i /> REFLEX AGENT / LIVE SIGNAL</div>
    </div>
  );
}

export default function Home() {
  const [activeSection, setActiveSection] = React.useState("introduction");
  const [menuOpen, setMenuOpen] = React.useState(false);

  React.useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) setActiveSection(visible.target.id);
    }, { rootMargin: "-18% 0px -58% 0px", threshold: [0, 0.15, 0.35, 0.6] });
    sections.forEach(({ id }) => {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    });
    return () => {
      observer.disconnect();
    };
  }, []);

  return (
    <div className="site-shell">
      <aside className="side-rail" aria-label="Page navigation">
        <a className="brand-lockup" href="#introduction" aria-label="Reflex home">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.svg" alt="Reflex Harness" width="148" height="48" />
        </a>

        <div className="rail-index-label"><span>INDEX</span></div>
        <nav className="rail-nav">
          {sections.map(({ id, label }, i) => (
            <a key={id} href={"#" + id} className={activeSection === id ? "is-active" : ""} onClick={() => setMenuOpen(false)}>
              <span>{String(i + 1).padStart(2, "0")}</span>{label}
            </a>
          ))}
        </nav>

        <div className="rail-bottom">
          <a className="rail-docs-link" href="#ship-it"><span className="rail-doc-icon">↗</span><span>Explore Reflex</span><b>→</b></a>
          <div className="rail-github-card">
            <div className="rail-github-title"><span className="github-mark">◉</span><span>OlegSavchuk / reflex-harness</span></div>
            <p>An evidence-driven harness that helps coding agents break out of failed loops.</p>
            <a href={GITHUB} target="_blank" rel="noopener noreferrer"><span>★</span> View on GitHub <span className="rail-external">↗</span></a>
          </div>
          <div className="rail-meta"><span>OPEN SOURCE</span><span>2026</span></div>
        </div>
      </aside>

      <header className="mobile-header">
        <a className="brand-lockup" href="#introduction" aria-label="Reflex home">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.svg" alt="Reflex Harness" width="130" height="42" />
        </a>
        <button className="mobile-menu-button" onClick={() => setMenuOpen((open) => !open)} aria-expanded={menuOpen} aria-label="Toggle page index">
          <span>{menuOpen ? "CLOSE" : "INDEX"}</span><b>{menuOpen ? "×" : "☰"}</b>
        </button>
        {menuOpen && <nav className="mobile-index">{sections.map(({ id, label }, i) => <a key={id} href={"#" + id} onClick={() => setMenuOpen(false)}><span>{String(i + 1).padStart(2, "0")}</span>{label}</a>)}</nav>}
      </header>

      <main className="main-stage">
        <section id="introduction" className="hero-frame frame-panel">
          <div className="hero-copy">
            <div className="hero-eyebrow"><i /> AGENT HARNESS ENGINEERING</div>
            <h1>Coding agents<br />get stuck in <span>loops.</span></h1>
            <p className="hero-lede">Reflex notices when an agent repeats a failed strategy, then changes its working context using evidence from earlier attempts.</p>
            <p className="hero-subcopy">A MongoDB-powered harness for persistent, measurable software development. Built for agents that need to recover, not just retry.</p>
            <div className="hero-command">
              <div className="command-tabs"><span>GET STARTED</span><span className="command-language">PYTHON CLI</span></div>
              <div className="command-row"><span className="command-prompt">$</span><code>git clone https://github.com/OlegSavchuk/reflex-harness.git && cd reflex-harness</code><span className="command-note">CLONE</span></div>
              <div className="command-row command-row-run"><span className="command-prompt">$</span><code>python -m reflex_harness run --task sem-dev-01 --arm memory</code><span className="command-note">RUN DEV TASK</span></div>
              <div className="command-help">After README setup: install deps, configure Atlas + model keys, seed memory · Python 3.10+</div>
            </div>
            <div className="hero-links"><a className="text-link text-link-blue" href={`${GITHUB}#reproduce`} target="_blank" rel="noopener noreferrer">Full setup guide <span>↗</span></a><a className="text-link" href="#features">See how it works <span>→</span></a></div>
          </div>
          <div className="hero-art-wrap"><GlyphAgent /></div>
          <div className="hero-frame-foot"><span><b>01</b> / 07</span><span>THE AGENT RECOVERY LOOP</span><span>REFLEX · 2026</span></div>
        </section>

        <div className="trust-strip frame-panel">
          <div className="trust-current"><span className="trust-tick"/><span className="trust-number">01 / 07</span><span className="trust-label">BUILT WITH</span></div>
          <div className="tech-logos" aria-label="Technology partners">
            {[
              { src: "/logos/mongodb.svg", alt: "MongoDB", h: 38 },
              { src: "/logos/voyage.svg", alt: "Voyage AI", h: 34 },
              { src: "/logos/open_router.svg", alt: "OpenRouter", h: 34 },
              { src: "/logos/jev.webp", alt: "TypeSafe AI", h: 34 },
              { src: "/logos/py_test.svg", alt: "pytest", h: 35 },
            ].map(({ src, alt, h }) => <img key={alt} src={src} alt={alt} style={{ height: h }} />)}
          </div>
        </div>
        <div className="stat-row frame-panel">
          <div><span>01</span><b>Controller</b><small>Owns the attempt loop</small></div>
          <div><span>02</span><b>Evidence</b><small>Tests and attempt history</small></div>
          <div><span>03</span><b>Context</b><small>Selected from what worked</small></div>
          <div><span>04</span><b>Recovery</b><small>Switch before the next retry</small></div>
        </div>

        <section id="features" className="content-frame frame-panel">
          <SectionHeading number="02" eyebrow="WHY THIS MATTERS" title="The loop is real. So is the cost." detail="Ilya Sutskever described the failure pattern plainly: one fix introduces another bug, and repairing that bug brings the first one back." />
          <div className="quote-layout">
            <figure className="ilya-quote">
              <span className="quote-mark">“</span>
              <blockquote>You tell the model <em>can you please fix the bug</em> — and it introduces a second bug. Then you tell it you have a second bug and it brings back the first. <strong>You can alternate between those.</strong></blockquote>
              <figcaption><b>Ilya Sutskever</b><span>Co-founder, OpenAI · SSI</span></figcaption>
              <a className="text-link text-link-blue quote-link" href={SHORT} target="_blank" rel="noopener noreferrer">Watch the original YouTube Short <span>↗</span></a>
            </figure>
            <div className="short-video-wrap">
              <div className="video-label"><span>FROM THE ORIGINAL CLIP</span><span>00:35</span></div>
              <div className="short-video"><iframe src="https://www.youtube.com/embed/aIvHf8vsWBM" title="Ilya Sutskever on coding-agent regressions" allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerPolicy="strict-origin-when-cross-origin" allowFullScreen /></div>
              <a className="video-caption" href={SHORT} target="_blank" rel="noopener noreferrer">Open the Short on YouTube <span>↗</span></a>
            </div>
          </div>
          <div className="feature-card-row">
            {[
              ["01", "Detect repetition", "Compare the latest attempt with prior failures to catch strategy oscillation."],
              ["02", "Change context", "Select from context configurations with evidence of success on similar failures."],
              ["03", "Keep the record", "Store attempts and outcomes so each decision can be inspected and measured."],
            ].map(([n, title, text]) => <article className="feature-card" key={n}><span>{n}</span><h3>{title}</h3><p>{text}</p></article>)}
          </div>
        </section>

        <section id="compare" className="content-frame frame-panel">
          <SectionHeading number="03" eyebrow="WHAT REFLEX DOES" title="A harness around the agent." />
          <div className="compare-grid">
            <article className="compare-card compare-card-primary"><div className="compare-label"><span>01</span> REFLEX IS</div><ul><li>A controller that owns the attempt loop</li><li>Context selection based on recorded evidence</li><li>Bug fixing against a fixed test suite</li><li>A single process: CLI and dashboard</li><li>A harness that can adapt its own environment to the task</li></ul></article>
            <article className="compare-card"><div className="compare-label compare-label-muted"><span>02</span> REFLEX IS NOT</div><ul><li>A new coding model</li><li>An LLM guessing which prompt might help</li><li>A feature builder without a test signal</li><li>A VS Code extension or MCP tool</li><li>A tool the agent must remember to call</li></ul></article>
          </div>
        </section>

        <section id="benchmarks" className="content-frame frame-panel">
          <SectionHeading number="04" eyebrow="SYSTEM ARCHITECTURE" title="How the control loop works." detail="Every attempt is observed, recorded, and used to select the next context. The loop runs until a verified fix lands or the budget is spent." />
          <div className="arch-diagram-wrap">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/architecture.svg"
              alt="Reflex Harness architecture diagram: Controller selects context, Coding Model generates a patch, Test Runner evaluates it, Jev detects semantic loops, MongoDB Atlas stores attempt memory, Voyage AI provides embeddings. Evidence flows back to the Controller."
              className="arch-diagram"
              width="1000"
              height="570"
            />
          </div>

          <div className="gate8-results">
            <div className="gate8-heading">
              <div>
                <div className="section-heading-meta gate8-eyebrow"><span>GATE 8</span><i /> HELD-OUT FEASIBILITY EVALUATION</div>
                <h3>Verified fixes across four held-out tasks.</h3>
              </div>
              <div className="gate8-run-meta"><b>60</b><span>RUNS</span><i />4 TASKS <i />5 REPEATS</div>
            </div>

            <figure className="gate8-chart">
              <img src="/gate8-benchmarks.svg" alt="Gate 8 results: Reflex with memory verified 5 of 10 fixes for oscillation and 8 of 10 for semantic repetition, 13 of 20 overall, at $0.0366. Fixed fallback verified 4 of 20 at $0.0391. Plain retry verified 0 of 20 at $0.0647. In family A, 9 of 10 plain retry runs passed diagnostics but none passed protected verification." />
            </figure>

            <div className="gate8-arm-grid">
              {gate8Arms.map((arm, index) => (
                <article className={`gate8-arm gate8-arm-${arm.style}`} key={arm.name}>
                  <div className="gate8-arm-top"><span>{String(index + 1).padStart(2, "0")} / {arm.tag}</span><span className="gate8-arm-dot" /></div>
                  <h4>{arm.name}</h4>
                  <div className="gate8-total"><strong>{arm.total}<i>/20</i></strong><span>verified fixes</span></div>
                  <div className="gate8-total-track" aria-label={`${arm.total} of 20 runs verified`}><i style={{ width: `${arm.total * 5}%` }} /></div>
                  <div className="gate8-family-list">
                    <div className="gate8-family-row"><span>Oscillation</span><b>{arm.oscillation}<i>/10</i></b><span className="gate8-family-track"><i style={{ width: `${arm.oscillation * 10}%` }} /></span></div>
                    <div className="gate8-family-row"><span>Semantic repetition</span><b>{arm.repetition}<i>/10</i></b><span className="gate8-family-track"><i style={{ width: `${arm.repetition * 10}%` }} /></span></div>
                  </div>
                  <div className="gate8-cost"><span>Run cost <b>{arm.cost}</b></span><span>Per verified fix <b>{arm.perFix}</b></span></div>
                </article>
              ))}
            </div>

            <div className="gate8-verified-note"><span>VERIFIED FIX</span><p>Diagnostics, protected tests, and the static gaming check all passed.</p></div>
            <div className="gate8-caveats">
              <article><span>01 / SAMPLE</span><p>Two held-out tasks per family, repeated five times. Repeats share tasks, so effective N is 2 per family. This is feasibility evidence, not a significance claim.</p></article>
              <article><span>02 / COMPARISON</span><p>Fixed fallback cannot expose family B’s hidden helper. The fair random-choice reference (about 3.3/10) is analytical; it was not run.</p></article>
              <article><span>03 / SCOPE</span><p>Gate 8 measures strategy selection. It does not establish repeated-strategy detection on semantic-repetition tasks.</p></article>
            </div>
          </div>
        </section>

        <section id="hands" className="content-frame frame-panel">
          <SectionHeading number="05" eyebrow="UNDER THE HOOD" title="An attempt, with evidence at every step." />
          <div className="flow-grid">
            {[
              ["01", "Controller", "Selects a context configuration from prior outcomes on similar failures."],
              ["02", "Coding model", "Receives the assembled context and returns a patch."],
              ["03", "Test runner", "Runs pytest and records passes, failures, and regressions."],
              ["04", "Jev", "Checks whether a changed diff repeats a failed strategy."],
              ["05", "MongoDB Atlas", "Stores attempts and retrieves the evidence for the next selection."],
            ].map(([n, title, text], index) => <article className="flow-step" key={n}><span className="flow-count">{n}</span><span className={"flow-glyph flow-glyph-" + (index + 1)}><FlowIcon kind={index} /></span><h3>{title}</h3><p>{text}</p>{index < 4 && <span className="flow-connector">→</span>}</article>)}
          </div>
          <div className="architecture-caption"><span>THE CONTROL LOOP</span><span>OBSERVE → SELECT → TEST → REMEMBER</span></div>
        </section>

        <section id="cookbook" className="content-frame frame-panel">
          <SectionHeading number="06" eyebrow="TOOLS AND STACK" title="MongoDB is part of the control loop." compactMeta />
          <div className="cookbook-grid">
            {[
              { src: "/logos/mongodb.svg", alt: "MongoDB", name: "MongoDB Atlas 8.0", role: "Attempt memory · retrieval · selection" },
              { src: "/logos/voyage.svg", alt: "Voyage AI", name: "Voyage AI · voyage-4", role: "Semantic embeddings" },
              { src: "/logos/open_router.svg", alt: "OpenRouter", name: "OpenRouter", role: "Model routing" },
              { src: "/logos/jev.webp", alt: "TypeSafe AI", name: "Jev 1.13", role: "Semantic loop detection" },
              { src: "/logos/py_test.svg", alt: "pytest", name: "pytest", role: "Test oracle" },
            ].map(({ src, alt, name, role }) => <article className="stack-card" key={name}><div className="stack-logo"><img src={src} alt={alt} /></div><div><h3>{name}</h3><p>{role}</p></div><span className="stack-arrow">↗</span></article>)}
          </div>
          <div className="cookbook-note"><span className="note-mark">i</span><p>Reflex is an open source hackathon project. See the repository for setup details, current requirements, and implementation notes.</p><a href={GITHUB} target="_blank" rel="noopener noreferrer">Repository <span>↗</span></a></div>
        </section>

        <section id="ship-it" className="ship-frame frame-panel">
          <div className="ship-decoration" aria-hidden="true"><span>R</span><i/><i/><i/></div>
          <div className="ship-content"><div className="section-heading-meta"><span>07 / 07</span><i/> SHIP IT</div><h2>Break the loop.<br /><span>Keep the evidence.</span></h2><a className="ship-button" href={GITHUB} target="_blank" rel="noopener noreferrer"><span>Explore reflex-harness</span><b>↗</b></a></div>
          <div className="ship-bottom"><a className="brand-lockup" href="#introduction" aria-label="Reflex home"><img src="/logo.svg" alt="Reflex Harness" width="118" height="38"/></a><span>OPEN SOURCE · HARNESS ENGINEERING</span><a href={GITHUB} target="_blank" rel="noopener noreferrer">GITHUB ↗</a></div>
        </section>
        <footer className="page-footer"><span>© 2026 REFLEX HARNESS</span><span>BUILT BY OLEH SAVCHUK</span><a href="#introduction">BACK TO TOP ↑</a></footer>
      </main>
    </div>
  );
}
