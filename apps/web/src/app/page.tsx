import React from "react";
import { StatusBanner } from "../components/StatusBanner";
import { NutritionDemoForm } from "../components/NutritionDemoForm";

export default function HomePage() {
  return (
    <>
      <section className="hero" aria-labelledby="hero-heading">
        <p className="hero-tag">Empowering Indian Consumers</p>
        <h1 id="hero-heading">Know What Goes Into Your Food</h1>
        <p className="hero-description">
          healthyIndia is establishing an open, deterministic platform to help consumers in India
          decode packaged food nutrition labels, understand hidden additives, and make informed choices.
        </p>
      </section>

      <StatusBanner />

      <NutritionDemoForm />

      <section className="section-grid" aria-label="Project Principles and Roadmap" style={{ marginTop: "2rem" }}>
        <article className="card">
          <h2>Core Principles</h2>
          <ul>
            <li>
              <strong>Deterministic calculations:</strong> Nutrition analyses run in verified Python
              without paid generative-AI or probabilistic hallucination.
            </li>
            <li>
              <strong>No silent zeros:</strong> Missing or unreadable nutrition values are never
              assumed to be zero or invented.
            </li>
            <li>
              <strong>Truth in source:</strong> The user&apos;s physical package label remains the
              primary source of truth.
            </li>
            <li>
              <strong>Transparent evidence:</strong> Claims and thresholds will cite credible
              scientific standards (such as FSSAI/ICMR/WHO).
            </li>
          </ul>
        </article>

        <article className="card">
          <h2>Development Roadmap</h2>
          <ul className="feature-status-list">
            <li className="feature-status-item">
              <span>Monorepo &amp; Security Baseline</span>
              <span className="status-tag tag-ready">Phase 1 (Active)</span>
            </li>
            <li className="feature-status-item">
              <span>Replaceable OCR Adapter</span>
              <span className="status-tag tag-upcoming">Phase 2</span>
            </li>
            <li className="feature-status-item">
              <span>Deterministic Nutrition Engine</span>
              <span className="status-tag tag-upcoming">Phase 3</span>
            </li>
            <li className="feature-status-item">
              <span>Ingredient Knowledge Base</span>
              <span className="status-tag tag-upcoming">Phase 4</span>
            </li>
            <li className="feature-status-item">
              <span>User Accounts &amp; Persistence</span>
              <span className="status-tag tag-future">Post-MVP</span>
            </li>
          </ul>
        </article>
      </section>
    </>
  );
}
