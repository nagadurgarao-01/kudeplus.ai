import { useEffect, useState, useCallback, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import axios from 'axios';

const API = 'http://localhost:8000';

export default function App() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [graphData, setGraphData] = useState<any>({ nodes: [], links: [] });
  const [incidents, setIncidents] = useState<any[]>([]);
  const [wsStatus, setWsStatus] = useState('Connecting...');
  const [activeTab, setActiveTab] = useState<'alerts' | 'graph' | 'history'>('alerts');
  const graphRef = useRef<any>(null);

  // WebSocket for live alerts
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/alerts');
    ws.onopen = () => setWsStatus('🟢 Connected');
    ws.onclose = () => setWsStatus('🔴 Disconnected');
    ws.onerror = () => setWsStatus('🔴 Error');
    ws.onmessage = (e) => {
      const alert = JSON.parse(e.data);
      setAlerts(prev => [alert, ...prev].slice(0, 50));
    };
    return () => ws.close();
  }, []);

  // Fetch graph data every 15 seconds
  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const res = await axios.get(`${API}/api/graph`);
        const data = res.data;
        setGraphData({
          nodes: data.nodes || [],
          links: (data.edges || []).map((e: any) => ({
            source: e.source,
            target: e.target,
            value: Math.abs(e.weight)
          }))
        });
      } catch (err) {
        console.log('Graph fetch error:', err);
      }
    };
    fetchGraph();
    const interval = setInterval(fetchGraph, 15000);
    return () => clearInterval(interval);
  }, []);

  // Fetch incident history every 10 seconds
  useEffect(() => {
    const fetchIncidents = async () => {
      try {
        const res = await axios.get(`${API}/api/incidents?limit=30`);
        if (Array.isArray(res.data)) {
          setIncidents(res.data);
        }
      } catch (err) {
        console.log('Incidents fetch error:', err);
      }
    };
    fetchIncidents();
    const interval = setInterval(fetchIncidents, 10000);
    return () => clearInterval(interval);
  }, []);

  const nodeColor = useCallback((node: any) => {
    const inAlert = alerts.some(a => a.pod === node.id);
    return inAlert ? '#f85149' : '#58a6ff';
  }, [alerts]);

  const linkColor = useCallback((link: any) => {
    return link.value > 0.9 ? '#f85149' : '#3fb950';
  }, []);

  const tabStyle = (tab: string) => ({
    padding: '10px 24px',
    cursor: 'pointer',
    background: activeTab === tab ? '#21262d' : 'transparent',
    color: activeTab === tab ? '#58a6ff' : '#8b949e',
    border: 'none',
    borderBottom: activeTab === tab ? '2px solid #58a6ff' : '2px solid transparent',
    fontSize: '14px',
    fontFamily: 'monospace',
    fontWeight: activeTab === tab ? 'bold' as const : 'normal' as const,
  });

  const severityColor = (sev: string) => {
    switch (sev) {
      case 'CRITICAL': return '#f85149';
      case 'HIGH': return '#d29922';
      case 'MEDIUM': return '#3fb950';
      default: return '#8b949e';
    }
  };

  return (
    <div style={{ fontFamily: 'monospace', background: '#0d1117', minHeight: '100vh', color: '#c9d1d9' }}>

      {/* Header */}
      <div style={{ padding: '20px 24px', borderBottom: '1px solid #21262d', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ color: '#58a6ff', margin: 0, fontSize: '22px' }}>
            ⚡ KubePulse AI
          </h1>
          <p style={{ color: '#8b949e', margin: '4px 0 0 0', fontSize: '12px' }}>
            AIOps for Kubernetes Operations
          </p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <span style={{ fontSize: '12px' }}>{wsStatus}</span>
          <br />
          <span style={{ color: '#8b949e', fontSize: '11px' }}>
            {alerts.length} live alerts | {incidents.length} history | {graphData.nodes.length} pods tracked
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ borderBottom: '1px solid #21262d', display: 'flex' }}>
        <button style={tabStyle('alerts')} onClick={() => setActiveTab('alerts')}>
          🔔 Live Alerts ({alerts.length})
        </button>
        <button style={tabStyle('graph')} onClick={() => setActiveTab('graph')}>
          🔗 Pod Dependency Graph ({graphData.nodes.length} pods)
        </button>
        <button style={tabStyle('history')} onClick={() => setActiveTab('history')}>
          📋 Incident History ({incidents.length})
        </button>
      </div>

      {/* Content */}
      <div style={{ padding: 24 }}>

        {/* LIVE ALERTS TAB */}
        {activeTab === 'alerts' && (
          <div>
            {alerts.length === 0 && (
              <div style={{ color: '#8b949e', textAlign: 'center', padding: 40 }}>
                Waiting for alerts... Run <code>bash demo/chaos_inject.sh</code> to trigger alerts.
              </div>
            )}
            {alerts.map((a, i) => (
              <div key={i} style={{
                background: a.severity === 'CRITICAL' ? '#3d1f1f' : a.severity === 'HIGH' ? '#3d2f1f' : '#1a2a1a',
                margin: '8px 0', padding: 14,
                borderLeft: `4px solid ${severityColor(a.severity)}`,
                borderRadius: 6,
                transition: 'all 0.3s ease',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>
                    <b style={{ color: severityColor(a.severity), fontSize: '13px' }}>
                      {a.severity}
                    </b>
                    <span style={{ color: '#8b949e' }}> | </span>
                    <span style={{ color: '#c9d1d9' }}>{a.pod}</span>
                    <span style={{ color: '#8b949e' }}> | {a.namespace}</span>
                  </span>
                </div>
                <div style={{ color: '#8b949e', fontSize: '12px', marginTop: 6 }}>{a.reason}</div>
                {a.nlp_summary && (
                  <div style={{
                    color: '#58a6ff', fontSize: '12px', marginTop: 6,
                    padding: '6px 10px', background: '#161b22', borderRadius: 4,
                    borderLeft: '2px solid #58a6ff'
                  }}>
                    🤖 AI: {a.nlp_summary}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* POD DEPENDENCY GRAPH TAB */}
        {activeTab === 'graph' && (
          <div>
            <p style={{ color: '#8b949e', fontSize: '12px', marginBottom: 12 }}>
              Pods connected by Pearson correlation (r &gt; 0.85). Red = r &gt; 0.9, Green = r &gt; 0.85.
              Pods involved in active alerts are shown in red.
            </p>
            {graphData.nodes.length === 0 ? (
              <div style={{ color: '#8b949e', textAlign: 'center', padding: 40 }}>
                No correlated pods found yet. The correlation engine needs ~2 minutes of data to detect patterns.
              </div>
            ) : (
              <div style={{ background: '#161b22', borderRadius: 8, border: '1px solid #21262d' }}>
                <ForceGraph2D
                  ref={graphRef}
                  graphData={graphData}
                  nodeLabel="id"
                  nodeColor={nodeColor}
                  linkColor={linkColor}
                  linkWidth={(link: any) => link.value * 3}
                  linkLabel={(link: any) => `${link.source.id || link.source} ↔ ${link.target.id || link.target}  |  r = ${link.value.toFixed(3)}`}
                  nodeRelSize={8}
                  width={900}
                  height={500}
                  backgroundColor="#161b22"
                  nodeCanvasObject={(node: any, ctx: any, globalScale: number) => {
                    const label = node.id;
                    const fontSize = 11 / globalScale;
                    ctx.font = `${fontSize}px monospace`;

                    // Draw node circle
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, 6, 0, 2 * Math.PI);
                    ctx.fillStyle = nodeColor(node);
                    ctx.fill();
                    ctx.strokeStyle = '#21262d';
                    ctx.lineWidth = 1;
                    ctx.stroke();

                    // Draw label
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillStyle = '#c9d1d9';
                    ctx.fillText(label, node.x, node.y + 12);
                  }}
                />
              </div>
            )}
          </div>
        )}

        {/* INCIDENT HISTORY TAB */}
        {activeTab === 'history' && (
          <div>
            {incidents.length === 0 ? (
              <div style={{ color: '#8b949e', textAlign: 'center', padding: 40 }}>
                No incidents recorded in the database yet.
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #21262d', color: '#8b949e' }}>
                    <th style={{ padding: 8, textAlign: 'left' }}>Severity</th>
                    <th style={{ padding: 8, textAlign: 'left' }}>Pod</th>
                    <th style={{ padding: 8, textAlign: 'left' }}>Namespace</th>
                    <th style={{ padding: 8, textAlign: 'left' }}>Reason</th>
                    <th style={{ padding: 8, textAlign: 'left' }}>AI Summary</th>
                  </tr>
                </thead>
                <tbody>
                  {incidents.map((inc, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #161b22' }}>
                      <td style={{ padding: 8 }}>
                        <span style={{ color: severityColor(inc.severity), fontWeight: 'bold' }}>
                          {inc.severity}
                        </span>
                      </td>
                      <td style={{ padding: 8 }}>{inc.pod}</td>
                      <td style={{ padding: 8, color: '#8b949e' }}>{inc.namespace}</td>
                      <td style={{ padding: 8, color: '#8b949e' }}>{inc.reason}</td>
                      <td style={{ padding: 8, color: '#58a6ff' }}>{inc.nlp_summary || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
