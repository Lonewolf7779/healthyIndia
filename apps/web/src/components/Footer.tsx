import React from "react";

export const Footer: React.FC = () => {
  return (
    <footer className="site-footer" role="contentinfo">
      <div className="footer-container">
        <p className="footer-text">
          <strong>healthyIndia</strong> &mdash; Helping Indian consumers understand packaged food nutrition labels and ingredients.
        </p>
        <p className="footer-disclaimer">
          Transparency notice: Version 1 is deterministic and does not use paid generative-AI APIs. Missing nutrition values are never silently treated as zero.
        </p>
      </div>
    </footer>
  );
};
