import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const WS_BASE = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws/alerts';

interface AlertItem {
  pod: string;
  namespace?: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  reason: string;
  recommendation?: string;
  nlp_summary?: string;
  timestamp: number;
}

interface IncidentItem {
  id?: number;
  pod: string;
  namespace: string;
  severity: string;
  reason: string;
  recommendation?: string;
  nlp_summary?: string;
  timestamp: number;
}

export default function App() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [graphData, setGraphData] = useState<{ nodes: any[]; links: any[] }>({ nodes: [], links: [] });
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [wsStatus, setWsStatus] = useState<'connected' | 'connecting' | 'disconnected'>('connecting');
  const [activeTab, setActiveTab] = useState<'alerts' | 'graph' | 'history'>('alerts');
  const [selectedIncident, setSelectedIncident] = useState<AlertItem | IncidentItem | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState<'ALL' | 'CRITICAL' | 'HIGH' | 'MEDIUM'>('ALL');
  const [copiedText, setCopiedText] = useState<string | null>(null);
  const graphRef = useRef<any>(null);

  // WebSocket Live Alerts with Automatic Reconnection
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: NodeJS.Timeout | null = null;
    let isMounted = true;

    const connect = () => {
      if (!isMounted) return;
      try {
        setWsStatus('connecting');
        ws = new WebSocket(WS_BASE);

        ws.onopen = () => {
          if (isMounted) setWsStatus('connected');
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const newAlert: AlertItem = JSON.parse(event.data);
            setAlerts((prev) => [newAlert, ...prev.slice(0, 49)]);
          } catch (e) {
            console.error('Failed to parse incoming alert:', e);
          }
        };

        ws.onerror = () => {
          if (isMounted) setWsStatus('disconnected');
        };

        ws.onclose = () => {
          if (isMounted) {
            setWsStatus('disconnected');
            reconnectTimer = setTimeout(connect, 3000);
          }
        };
      } catch (err) {
        if (isMounted) {
          setWsStatus('disconnected');
          reconnectTimer = setTimeout(connect, 3000);
        }
      }
    };

    connect();

    return () => {
      isMounted = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  // Fetch Graph Data Periodically
  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/graph`);
        const data = res.data;
        setGraphData({
          nodes: (data.nodes || []).map((n: any) => ({
            id: n.id,
            name: n.id,
          })),
          links: (data.edges || []).map((e: any) => ({
            source: e.source,
            target: e.target,
            value: Math.abs(e.weight || 1.0),
          })),
        });
      } catch (err) {
        console.error('Graph fetch error:', err);
      }
    };

    fetchGraph();
    const interval = setInterval(fetchGraph, 10000);
    return () => clearInterval(interval);
  }, []);

  // Fetch Incident History Periodically
  useEffect(() => {
    const fetchIncidents = async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/incidents?limit=50`);
        if (Array.isArray(res.data)) {
          setIncidents(res.data);
        }
      } catch (err) {
        console.error('Incidents fetch error:', err);
      }
    };

    fetchIncidents();
    const interval = setInterval(fetchIncidents, 10000);
    return () => clearInterval(interval);
  }, []);

  // Copy helper
  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(text);
    setTimeout(() => setCopiedText(null), 2000);
  };

  // Severity color mapping (Apple HIG System Palette)
  const getSeverityTheme = (sev: string) => {
    switch (sev?.toUpperCase()) {
      case 'CRITICAL':
        return {
          color: 'var(--apple-red)',
          bg: 'rgba(255, 69, 58, 0.12)',
          border: 'rgba(255, 69, 58, 0.3)',
          label: 'Critical',
        };
      case 'HIGH':
        return {
          color: 'var(--apple-orange)',
          bg: 'rgba(255, 159, 10, 0.12)',
          border: 'rgba(255, 159, 10, 0.3)',
          label: 'High',
        };
      case 'MEDIUM':
        return {
          color: 'var(--apple-teal)',
          bg: 'rgba(100, 210, 255, 0.12)',
          border: 'rgba(100, 210, 255, 0.3)',
          label: 'Medium',
        };
      default:
        return {
          color: 'var(--apple-blue)',
          bg: 'rgba(10, 132, 255, 0.12)',
          border: 'rgba(10, 132, 255, 0.3)',
          label: sev || 'Info',
        };
    }
  };

  // Format relative timestamps
  const formatTime = (ts: number) => {
    if (!ts) return 'Just now';
    const diff = Math.floor(Date.now() / 1000 - ts);
    if (diff < 10) return 'Just now';
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  // Filtered Alerts & Incidents
  const filteredAlerts = useMemo(() => {
    return alerts.filter((a) => {
      const matchSeverity = severityFilter === 'ALL' || a.severity === severityFilter;
      const matchQuery =
        !searchQuery ||
        a.pod.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.reason.toLowerCase().includes(searchQuery.toLowerCase());
      return matchSeverity && matchQuery;
    });
  }, [alerts, severityFilter, searchQuery]);

  const filteredIncidents = useMemo(() => {
    return incidents.filter((i) => {
      const matchSeverity = severityFilter === 'ALL' || i.severity === severityFilter;
      const matchQuery =
        !searchQuery ||
        i.pod.toLowerCase().includes(searchQuery.toLowerCase()) ||
        i.reason.toLowerCase().includes(searchQuery.toLowerCase());
      return matchSeverity && matchQuery;
    });
  }, [incidents, severityFilter, searchQuery]);

  // Cluster Health Metrics
  const criticalCount = alerts.filter((a) => a.severity === 'CRITICAL').length;
  const highCount = alerts.filter((a) => a.severity === 'HIGH').length;
  const healthScore = Math.max(0, 100 - criticalCount * 25 - highCount * 10);

  // Graph Canvas Node Renderer
  const nodeColor = useCallback(
    (node: any) => {
      const isCritical = alerts.some((a) => a.pod === node.id && a.severity === 'CRITICAL');
      const isHigh = alerts.some((a) => a.pod === node.id && a.severity === 'HIGH');
      if (isCritical) return '#FF453A';
      if (isHigh) return '#FF9F0A';
      return '#0A84FF';
    },
    [alerts]
  );

  return (
    <div style={{ minHeight: '100vh', background: 'radial-gradient(ellipse at 50% 0%, #10141e 0%, #000000 70%)', color: 'var(--apple-text-primary)' }}>
      
      {/* 1. TOP NAVIGATION BAR (Apple macOS Translucent Bar) */}
      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 100,
          padding: '12px 28px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backdropFilter: 'blur(28px) saturate(190%)',
          WebkitBackdropFilter: 'blur(28px) saturate(190%)',
          backgroundColor: 'rgba(10, 12, 16, 0.75)',
          borderBottom: '1px solid var(--apple-border)',
        }}
      >
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '34px',
              height: '34px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #0A84FF 0%, #5E5CE6 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(10, 132, 255, 0.3)',
              fontSize: '18px',
            }}
          >
            ⚡
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '17px', fontWeight: '700', letterSpacing: '-0.02em' }}>KubePulse</span>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: '600',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  background: 'rgba(255, 255, 255, 0.08)',
                  padding: '2px 6px',
                  borderRadius: '6px',
                  color: 'var(--apple-text-secondary)',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                }}
              >
                AIOps Pro
              </span>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--apple-text-secondary)', margin: 0 }}>
              Automated Kubernetes Incident Intelligence
            </p>
          </div>
        </div>

        {/* Apple Segmented Control */}
        <div
          style={{
            display: 'flex',
            background: 'rgba(255, 255, 255, 0.06)',
            padding: '3px',
            borderRadius: '10px',
            border: '1px solid rgba(255, 255, 255, 0.08)',
          }}
        >
          <button
            onClick={() => setActiveTab('alerts')}
            style={{
              padding: '6px 18px',
              borderRadius: '8px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: '500',
              color: activeTab === 'alerts' ? '#FFFFFF' : 'var(--apple-text-secondary)',
              background: activeTab === 'alerts' ? 'rgba(255, 255, 255, 0.16)' : 'transparent',
              boxShadow: activeTab === 'alerts' ? '0 2px 8px rgba(0, 0, 0, 0.3)' : 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>🔔</span> Live Alerts
            {alerts.length > 0 && (
              <span
                style={{
                  background: criticalCount > 0 ? 'var(--apple-red)' : 'var(--apple-blue)',
                  color: '#fff',
                  fontSize: '10px',
                  fontWeight: '700',
                  padding: '1px 6px',
                  borderRadius: '10px',
                }}
              >
                {alerts.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('graph')}
            style={{
              padding: '6px 18px',
              borderRadius: '8px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: '500',
              color: activeTab === 'graph' ? '#FFFFFF' : 'var(--apple-text-secondary)',
              background: activeTab === 'graph' ? 'rgba(255, 255, 255, 0.16)' : 'transparent',
              boxShadow: activeTab === 'graph' ? '0 2px 8px rgba(0, 0, 0, 0.3)' : 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>🔗</span> Pod Topology
          </button>

          <button
            onClick={() => setActiveTab('history')}
            style={{
              padding: '6px 18px',
              borderRadius: '8px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: '500',
              color: activeTab === 'history' ? '#FFFFFF' : 'var(--apple-text-secondary)',
              background: activeTab === 'history' ? 'rgba(255, 255, 255, 0.16)' : 'transparent',
              boxShadow: activeTab === 'history' ? '0 2px 8px rgba(0, 0, 0, 0.3)' : 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>📋</span> Incident Log
          </button>
        </div>

        {/* Live Status Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              background: 'rgba(255, 255, 255, 0.04)',
              padding: '6px 14px',
              borderRadius: '20px',
              border: '1px solid var(--apple-border)',
              fontSize: '12px',
            }}
          >
            <span
              className="pulse-dot"
              style={{
                backgroundColor:
                  wsStatus === 'connected'
                    ? 'var(--apple-green)'
                    : wsStatus === 'connecting'
                    ? 'var(--apple-orange)'
                    : 'var(--apple-red)',
              }}
            />
            <span style={{ color: 'var(--apple-text-secondary)', fontWeight: '500' }}>
              {wsStatus === 'connected' ? 'Live Telemetry Active' : wsStatus === 'connecting' ? 'Connecting...' : 'Disconnected'}
            </span>
          </div>
        </div>
      </header>

      {/* 2. EXECUTIVE HIG OVERVIEW STATS */}
      <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px 28px' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '16px',
            marginBottom: '24px',
          }}
        >
          {/* Card 1: Cluster Health */}
          <div
            className="apple-glass"
            style={{
              padding: '20px',
              borderRadius: '16px',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <span style={{ fontSize: '13px', color: 'var(--apple-text-secondary)', fontWeight: '500' }}>
                Cluster Health Score
              </span>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: '600',
                  color: healthScore > 80 ? 'var(--apple-green)' : 'var(--apple-red)',
                  background: healthScore > 80 ? 'var(--apple-green-subtle)' : 'var(--apple-red-subtle)',
                  padding: '2px 8px',
                  borderRadius: '12px',
                }}
              >
                {healthScore > 80 ? 'Optimal' : 'Degraded'}
              </span>
            </div>
            <div style={{ fontSize: '32px', fontWeight: '700', margin: '8px 0 6px 0', letterSpacing: '-0.03em' }}>
              {healthScore}%
            </div>
            <div style={{ width: '100%', height: '4px', background: 'rgba(255, 255, 255, 0.08)', borderRadius: '2px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${healthScore}%`,
                  height: '100%',
                  background: healthScore > 80 ? 'var(--apple-green)' : 'var(--apple-red)',
                  transition: 'width 0.5s ease',
                }}
              />
            </div>
          </div>

          {/* Card 2: Active Alerts */}
          <div
            className="apple-glass"
            style={{
              padding: '20px',
              borderRadius: '16px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <span style={{ fontSize: '13px', color: 'var(--apple-text-secondary)', fontWeight: '500' }}>
                Active Anomalies
              </span>
              <span style={{ fontSize: '18px' }}>⚠️</span>
            </div>
            <div style={{ fontSize: '32px', fontWeight: '700', margin: '8px 0 4px 0', letterSpacing: '-0.03em' }}>
              {alerts.length}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--apple-text-secondary)' }}>
              <span style={{ color: 'var(--apple-red)', fontWeight: '600' }}>{criticalCount} Critical</span> ·{' '}
              <span style={{ color: 'var(--apple-orange)', fontWeight: '600' }}>{highCount} High</span>
            </div>
          </div>

          {/* Card 3: Pod Nodes Tracked */}
          <div
            className="apple-glass"
            style={{
              padding: '20px',
              borderRadius: '16px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <span style={{ fontSize: '13px', color: 'var(--apple-text-secondary)', fontWeight: '500' }}>
                Monitored Pods
              </span>
              <span style={{ fontSize: '18px' }}>📦</span>
            </div>
            <div style={{ fontSize: '32px', fontWeight: '700', margin: '8px 0 4px 0', letterSpacing: '-0.03em' }}>
              {graphData.nodes.length}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--apple-text-secondary)' }}>
              {graphData.links.length} cross-pod correlation links
            </div>
          </div>

          {/* Card 4: AI Incident Intelligence */}
          <div
            className="apple-glass"
            style={{
              padding: '20px',
              borderRadius: '16px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <span style={{ fontSize: '13px', color: 'var(--apple-text-secondary)', fontWeight: '500' }}>
                AI SRE Intelligence
              </span>
              <span style={{ fontSize: '18px' }}>🤖</span>
            </div>
            <div style={{ fontSize: '32px', fontWeight: '700', margin: '8px 0 4px 0', letterSpacing: '-0.03em', color: '#9d9aff' }}>
              {incidents.length}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--apple-text-secondary)' }}>
              Enriched with local Ollama engine
            </div>
          </div>
        </div>

        {/* 3. SEARCH & FILTER CONTROLS */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
            marginBottom: '20px',
          }}
        >
          {/* Search bar */}
          <div
            style={{
              position: 'relative',
              width: '320px',
            }}
          >
            <input
              type="text"
              placeholder="Search pod or anomaly..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 14px 8px 34px',
                borderRadius: '10px',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid var(--apple-border)',
                color: 'var(--apple-text-primary)',
                fontSize: '13px',
                fontFamily: 'var(--font-sans)',
                outline: 'none',
              }}
            />
            <span
              style={{
                position: 'absolute',
                left: '11px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--apple-text-tertiary)',
                fontSize: '13px',
              }}
            >
              🔍
            </span>
          </div>

          {/* Filter Pills */}
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {(['ALL', 'CRITICAL', 'HIGH', 'MEDIUM'] as const).map((sev) => (
              <button
                key={sev}
                onClick={() => setSeverityFilter(sev)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '14px',
                  border: '1px solid',
                  borderColor:
                    severityFilter === sev
                      ? sev === 'CRITICAL'
                        ? 'var(--apple-red)'
                        : sev === 'HIGH'
                        ? 'var(--apple-orange)'
                        : 'var(--apple-blue)'
                      : 'var(--apple-border)',
                  background:
                    severityFilter === sev
                      ? sev === 'CRITICAL'
                        ? 'var(--apple-red-subtle)'
                        : sev === 'HIGH'
                        ? 'var(--apple-orange-subtle)'
                        : 'var(--apple-blue-subtle)'
                      : 'rgba(255, 255, 255, 0.03)',
                  color:
                    severityFilter === sev
                      ? sev === 'CRITICAL'
                        ? 'var(--apple-red)'
                        : sev === 'HIGH'
                        ? 'var(--apple-orange)'
                        : 'var(--apple-blue)'
                      : 'var(--apple-text-secondary)',
                  fontSize: '12px',
                  fontWeight: '500',
                  cursor: 'pointer',
                }}
              >
                {sev === 'ALL' ? 'All Severities' : sev}
              </button>
            ))}
          </div>
        </div>

        {/* 4. MAIN CONTENT TABS */}

        {/* TAB 1: LIVE ALERTS FEED */}
        {activeTab === 'alerts' && (
          <div>
            {filteredAlerts.length === 0 ? (
              <div
                className="apple-glass"
                style={{
                  padding: '80px 20px',
                  borderRadius: '16px',
                  textAlign: 'center',
                  color: 'var(--apple-text-secondary)',
                }}
              >
                <div style={{ fontSize: '36px', marginBottom: '12px' }}>✨</div>
                <h3 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--apple-text-primary)', marginBottom: '6px' }}>
                  All Pods Healthy
                </h3>
                <p style={{ fontSize: '13px', maxWidth: '420px', margin: '0 auto 16px auto' }}>
                  No active anomalies detected in current stream windows. Run chaos scripts to simulate cluster distress.
                </p>
                <code
                  onClick={() => handleCopy('bash demo/chaos_inject.sh')}
                  style={{
                    display: 'inline-block',
                    background: 'rgba(255, 255, 255, 0.06)',
                    padding: '8px 16px',
                    borderRadius: '8px',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--apple-blue)',
                    cursor: 'pointer',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                  }}
                >
                  {copiedText === 'bash demo/chaos_inject.sh' ? '✓ Copied to clipboard!' : 'bash demo/chaos_inject.sh'}
                </code>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {filteredAlerts.map((alert, idx) => {
                  const theme = getSeverityTheme(alert.severity);
                  return (
                    <div
                      key={idx}
                      onClick={() => setSelectedIncident(alert)}
                      className="apple-glass interactive-card"
                      style={{
                        padding: '18px 22px',
                        borderRadius: '16px',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '10px',
                        borderLeft: `4px solid ${theme.color}`,
                      }}
                    >
                      {/* Alert Header */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span
                            style={{
                              background: theme.bg,
                              color: theme.color,
                              border: `1px solid ${theme.border}`,
                              padding: '2px 8px',
                              borderRadius: '6px',
                              fontSize: '11px',
                              fontWeight: '700',
                              textTransform: 'uppercase',
                              letterSpacing: '0.04em',
                            }}
                          >
                            {alert.severity}
                          </span>
                          <span style={{ fontSize: '15px', fontWeight: '600', color: '#FFFFFF' }}>
                            {alert.pod}
                          </span>
                          <span
                            style={{
                              fontSize: '12px',
                              color: 'var(--apple-text-secondary)',
                              background: 'rgba(255, 255, 255, 0.05)',
                              padding: '2px 8px',
                              borderRadius: '6px',
                            }}
                          >
                            ns: {alert.namespace || 'default'}
                          </span>
                        </div>
                        <span style={{ fontSize: '12px', color: 'var(--apple-text-tertiary)' }}>
                          {formatTime(alert.timestamp)}
                        </span>
                      </div>

                      {/* Alert Reason */}
                      <div style={{ fontSize: '13px', color: 'var(--apple-text-primary)', lineHeight: '1.4' }}>
                        {alert.reason}
                      </div>

                      {/* AI Intelligence Card */}
                      {alert.nlp_summary && (
                        <div
                          style={{
                            background: 'rgba(10, 132, 255, 0.06)',
                            border: '1px solid rgba(10, 132, 255, 0.15)',
                            padding: '10px 14px',
                            borderRadius: '10px',
                            display: 'flex',
                            gap: '10px',
                            alignItems: 'flex-start',
                          }}
                        >
                          <span style={{ fontSize: '16px' }}>🤖</span>
                          <div style={{ fontSize: '12px', color: '#D1E6FF', lineHeight: '1.5' }}>
                            <strong style={{ color: 'var(--apple-blue)' }}>AI Remediation: </strong>
                            {alert.nlp_summary}
                          </div>
                        </div>
                      )}

                      {/* Action snippet */}
                      {alert.recommendation && (
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '4px' }}>
                          <span style={{ fontSize: '12px', color: 'var(--apple-text-secondary)' }}>
                            💡 <b>Suggested Action:</b> {alert.recommendation}
                          </span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCopy(`kubectl logs ${alert.pod} -n ${alert.namespace || 'default'}`);
                            }}
                            style={{
                              background: 'rgba(255, 255, 255, 0.06)',
                              border: '1px solid var(--apple-border)',
                              padding: '4px 10px',
                              borderRadius: '6px',
                              color: 'var(--apple-text-primary)',
                              fontSize: '11px',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <span>📋</span> Copy Diagnostic CLI
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: POD DEPENDENCY TOPOLOGY */}
        {activeTab === 'graph' && (
          <div>
            <div
              className="apple-glass"
              style={{
                borderRadius: '16px',
                padding: '24px',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '4px' }}>
                    Live Cross-Signal Correlation Graph
                  </h3>
                  <p style={{ fontSize: '12px', color: 'var(--apple-text-secondary)', margin: 0 }}>
                    Nodes represent cluster workloads. Edges represent dynamic Pearson correlation ($|r| &gt; 0.85$). Nodes with active anomalies appear highlighted.
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => graphRef.current?.zoomToFit(400)}
                    style={{
                      background: 'rgba(255, 255, 255, 0.06)',
                      border: '1px solid var(--apple-border)',
                      padding: '6px 12px',
                      borderRadius: '8px',
                      color: 'var(--apple-text-primary)',
                      fontSize: '12px',
                      cursor: 'pointer',
                    }}
                  >
                    Fit View
                  </button>
                </div>
              </div>

              {graphData.nodes.length === 0 ? (
                <div style={{ padding: '80px 20px', textAlign: 'center', color: 'var(--apple-text-secondary)' }}>
                  No active pod signals detected. The correlation processor requires ~1 minute of telemetry streams.
                </div>
              ) : (
                <div style={{ background: '#090a0f', borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
                  <ForceGraph2D
                    ref={graphRef}
                    graphData={graphData}
                    nodeLabel="name"
                    nodeColor={nodeColor}
                    linkColor={(link: any) => (link.value > 0.9 ? 'rgba(255, 69, 58, 0.7)' : 'rgba(48, 209, 88, 0.5)')}
                    linkWidth={(link: any) => Math.max(1.5, (link.value || 1) * 3)}
                    linkLabel={(link: any) => `${link.source.id || link.source} ↔ ${link.target.id || link.target} (Pearson r = ${Number(link.value).toFixed(3)})`}
                    width={1300}
                    height={580}
                    backgroundColor="#090a0f"
                    nodeCanvasObject={(node: any, ctx: any, globalScale: number) => {
                      const label = node.id;
                      const fontSize = 12 / globalScale;
                      ctx.font = `${fontSize}px -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif`;

                      // Ambient glow
                      const color = nodeColor(node);
                      ctx.shadowColor = color;
                      ctx.shadowBlur = 10;

                      // Draw circular node
                      ctx.beginPath();
                      ctx.arc(node.x, node.y, 7, 0, 2 * Math.PI);
                      ctx.fillStyle = color;
                      ctx.fill();
                      ctx.strokeStyle = '#FFFFFF';
                      ctx.lineWidth = 1.5;
                      ctx.stroke();

                      // Reset shadow for text
                      ctx.shadowBlur = 0;

                      // Node label
                      ctx.textAlign = 'center';
                      ctx.textBaseline = 'middle';
                      ctx.fillStyle = '#E5E5EA';
                      ctx.fillText(label, node.x, node.y + 14);
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: INCIDENT HISTORY LOG (APPLE HIG TABLE VIEW) */}
        {activeTab === 'history' && (
          <div className="apple-glass" style={{ borderRadius: '16px', overflow: 'hidden' }}>
            {filteredIncidents.length === 0 ? (
              <div style={{ padding: '80px 20px', textAlign: 'center', color: 'var(--apple-text-secondary)' }}>
                No historical incidents stored in SQLite database.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--apple-border)', background: 'rgba(255, 255, 255, 0.02)', color: 'var(--apple-text-secondary)' }}>
                      <th style={{ padding: '14px 20px', fontWeight: '500' }}>Time</th>
                      <th style={{ padding: '14px 20px', fontWeight: '500' }}>Severity</th>
                      <th style={{ padding: '14px 20px', fontWeight: '500' }}>Pod Workload</th>
                      <th style={{ padding: '14px 20px', fontWeight: '500' }}>Trigger Reason</th>
                      <th style={{ padding: '14px 20px', fontWeight: '500' }}>AI Remediation Summary</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredIncidents.map((inc, i) => {
                      const theme = getSeverityTheme(inc.severity);
                      return (
                        <tr
                          key={i}
                          onClick={() => setSelectedIncident(inc)}
                          style={{
                            borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                            background: i % 2 === 0 ? 'transparent' : 'rgba(255, 255, 255, 0.01)',
                            cursor: 'pointer',
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)')}
                          onMouseLeave={(e) =>
                            (e.currentTarget.style.background = i % 2 === 0 ? 'transparent' : 'rgba(255, 255, 255, 0.01)')
                          }
                        >
                          <td style={{ padding: '14px 20px', color: 'var(--apple-text-tertiary)', whiteSpace: 'nowrap', fontSize: '12px' }}>
                            {formatTime(inc.timestamp)}
                          </td>
                          <td style={{ padding: '14px 20px' }}>
                            <span
                              style={{
                                background: theme.bg,
                                color: theme.color,
                                border: `1px solid ${theme.border}`,
                                padding: '2px 8px',
                                borderRadius: '6px',
                                fontSize: '11px',
                                fontWeight: '700',
                              }}
                            >
                              {inc.severity}
                            </span>
                          </td>
                          <td style={{ padding: '14px 20px', color: '#FFFFFF', fontWeight: '600' }}>
                            {inc.pod}
                            <span style={{ display: 'block', fontSize: '11px', color: 'var(--apple-text-secondary)', fontWeight: 'normal' }}>
                              ns: {inc.namespace || 'default'}
                            </span>
                          </td>
                          <td style={{ padding: '14px 20px', color: 'var(--apple-text-primary)' }}>
                            {inc.reason}
                          </td>
                          <td style={{ padding: '14px 20px', color: '#A0C7FF', maxWidth: '380px', lineHeight: '1.4' }}>
                            {inc.nlp_summary || '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </main>

      {/* 5. APPLE DETAIL INSPECTOR SHEET (SLIDE-OVER DRAWER) */}
      {selectedIncident && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.6)',
            backdropFilter: 'blur(10px)',
            WebkitBackdropFilter: 'blur(10px)',
            zIndex: 1000,
            display: 'flex',
            justifyContent: 'flex-end',
          }}
          onClick={() => setSelectedIncident(null)}
        >
          <div
            className="apple-glass-elevated"
            style={{
              width: '480px',
              maxWidth: '90vw',
              height: '100vh',
              padding: '28px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              borderLeft: '1px solid var(--apple-border-strong)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drawer Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span
                  style={{
                    background: getSeverityTheme(selectedIncident.severity).bg,
                    color: getSeverityTheme(selectedIncident.severity).color,
                    border: `1px solid ${getSeverityTheme(selectedIncident.severity).border}`,
                    padding: '3px 8px',
                    borderRadius: '6px',
                    fontSize: '11px',
                    fontWeight: '700',
                  }}
                >
                  {selectedIncident.severity}
                </span>
                <h2 style={{ fontSize: '20px', fontWeight: '700', marginTop: '8px', color: '#FFFFFF' }}>
                  {selectedIncident.pod}
                </h2>
              </div>
              <button
                onClick={() => setSelectedIncident(null)}
                style={{
                  background: 'rgba(255, 255, 255, 0.08)',
                  border: 'none',
                  color: 'var(--apple-text-secondary)',
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  cursor: 'pointer',
                  fontSize: '16px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                ✕
              </button>
            </div>

            {/* Diagnostic Details */}
            <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '16px', borderRadius: '12px', border: '1px solid var(--apple-border)' }}>
              <div style={{ fontSize: '11px', color: 'var(--apple-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                Anomaly Description
              </div>
              <div style={{ fontSize: '14px', lineHeight: '1.5' }}>{selectedIncident.reason}</div>
            </div>

            {/* AI Summary */}
            <div
              style={{
                background: 'linear-gradient(135deg, rgba(10, 132, 255, 0.08) 0%, rgba(94, 92, 230, 0.08) 100%)',
                padding: '18px',
                borderRadius: '12px',
                border: '1px solid rgba(10, 132, 255, 0.2)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <span style={{ fontSize: '16px' }}>🤖</span>
                <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--apple-blue)' }}>
                  Ollama AI SRE Analysis
                </span>
              </div>
              <p style={{ fontSize: '13px', color: '#DCE8FA', lineHeight: '1.6', margin: 0 }}>
                {selectedIncident.nlp_summary || 'AI synthesis pending or unavailable.'}
              </p>
            </div>

            {/* Recommended Action & Copy Command */}
            <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '16px', borderRadius: '12px', border: '1px solid var(--apple-border)' }}>
              <div style={{ fontSize: '11px', color: 'var(--apple-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                Mitigation & Remediation
              </div>
              <div style={{ fontSize: '13px', marginBottom: '12px', color: '#FFFFFF' }}>
                {selectedIncident.recommendation || 'Inspect pod container logs and verify resource constraints.'}
              </div>
              <div
                style={{
                  background: '#090a0f',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  color: 'var(--apple-teal)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                }}
              >
                <span>kubectl logs {selectedIncident.pod} -n {selectedIncident.namespace || 'default'}</span>
                <button
                  onClick={() => handleCopy(`kubectl logs ${selectedIncident.pod} -n ${selectedIncident.namespace || 'default'}`)}
                  style={{
                    background: 'rgba(255, 255, 255, 0.1)',
                    border: 'none',
                    color: '#FFF',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    fontSize: '10px',
                    cursor: 'pointer',
                  }}
                >
                  {copiedText?.includes(selectedIncident.pod) ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>

            {/* Metadata Footer */}
            <div style={{ marginTop: 'auto', fontSize: '11px', color: 'var(--apple-text-tertiary)' }}>
              Recorded: {new Date((selectedIncident.timestamp || Date.now() / 1000) * 1000).toLocaleString()}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
