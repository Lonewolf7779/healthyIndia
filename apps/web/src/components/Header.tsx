import React from "react";

export const Header: React.FC = () => {
  return (
    <header className="site-header" role="banner">
      <div className="header-container">
        <div className="brand">
          <span className="brand-logo" aria-hidden="true">🌱</span>
          <span className="brand-title">healthyIndia</span>
        </div>
        <nav aria-label="Main Navigation">
          <span className="badge">Phase 1 Foundation</span>
        </nav>
      </div>
    </header>
  );
};
