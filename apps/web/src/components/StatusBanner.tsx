"use client";

import React, { useEffect, useState } from "react";
import { apiClient, HealthResponse } from "../lib/api/client";

export const StatusBanner: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const checkConnection = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getHealth();
      setHealth(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Unable to connect to backend");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkConnection();
  }, []);

  return (
    <div className="status-banner" role="region" aria-label="System Status">
      <div className="status-content">
        <span className="status-label">Backend API Status:</span>
        {loading && <span className="status-pill status-loading">Checking connection...</span>}
        {!loading && health && (
          <span className="status-pill status-online">
            Online ({health.environment} v{health.version})
          </span>
        )}
        {!loading && error && (
          <span className="status-pill status-offline">
            Offline ({error})
          </span>
        )}
      </div>
      <button
        type="button"
        className="btn-retry"
        onClick={checkConnection}
        disabled={loading}
        aria-label="Recheck backend API connection"
      >
        Recheck API
      </button>
    </div>
  );
};
