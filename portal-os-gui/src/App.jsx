import { useMemo, useState } from 'react';
import { API_BASE_URL, UMBRELLA_LANES, callUmbrellaLane } from './api.js';

const DEFAULT_INPUT = '{\n  "subject": "portal-operator",\n  "facets": ["identity", "behavior", "structure"]\n}';

function App() {
  const [token, setToken] = useState('');
  const [tier, setTier] = useState('professional');
  const [input, setInput] = useState(DEFAULT_INPUT);
  const [activePath, setActivePath] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const endpointLabel = useMemo(() => {
    if (!API_BASE_URL) return 'API not configured';
    return API_BASE_URL.replace(/^https?:\/\//, '');
  }, []);

  async function runLane(lane) {
    setError('');
    setResult(null);
    setActivePath(lane.path);
    try {
      const parsedInput = JSON.parse(input);
      if (!parsedInput || Array.isArray(parsedInput) || typeof parsedInput !== 'object') {
        throw new Error('Input JSON must be an object.');
      }
      const response = await callUmbrellaLane(lane.path, { tier, input: parsedInput }, token);
      setResult({ lane, response });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unknown request error');
    } finally {
      setActivePath('');
    }
  }

  return (
    <main className="shell">
      <nav className="topbar" aria-label="Portal navigation">
        <a className="brand" href="#top" aria-label="Portal-OS home">
          <span className="brand-mark" aria-hidden="true"><span /></span>
          <span>PORTAL—OS</span>
        </a>
        <div className="system-state">
          <span className={`state-dot ${API_BASE_URL ? 'online' : ''}`} />
          {API_BASE_URL ? 'WORKER LINK READY' : 'CONFIGURATION REQUIRED'}
        </div>
      </nav>

      <section className="hero" id="top">
        <div className="eyebrow"><span>UMBRA / 04</span><span>OPERATIONS SURFACE</span></div>
        <div className="hero-grid">
          <div>
            <p className="kicker">Unified intelligence infrastructure</p>
            <h1>Operate across<br /><em>every lane.</em></h1>
          </div>
          <div className="hero-copy">
            <p>One controlled surface for identity, governance, simulation, market, crossworld, and structural truth operations.</p>
            <div className="endpoint-chip">
              <span className="pulse" />
              <span>{endpointLabel}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="console" aria-labelledby="console-heading">
        <div className="section-heading">
          <div>
            <span className="section-number">01</span>
            <h2 id="console-heading">Session parameters</h2>
          </div>
          <p>Credentials remain in memory and are never persisted by this console.</p>
        </div>
        <div className="parameter-grid">
          <label className="field wide">
            <span>Bearer token</span>
            <input
              type="password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="Enter a configured Portal identity token"
              autoComplete="off"
            />
          </label>
          <label className="field">
            <span>License tier</span>
            <select value={tier} onChange={(event) => setTier(event.target.value)}>
              <option value="basic">Basic</option>
              <option value="professional">Professional</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </label>
          <label className="field payload">
            <span>Operation input · JSON</span>
            <textarea value={input} onChange={(event) => setInput(event.target.value)} spellCheck="false" />
          </label>
        </div>
      </section>

      <section className="lanes" aria-labelledby="lanes-heading">
        <div className="section-heading">
          <div>
            <span className="section-number">02</span>
            <h2 id="lanes-heading">Umbrella lanes</h2>
          </div>
          <p>Every request forwards your bearer and requested tier unchanged to the kernel.</p>
        </div>
        <div className="lane-grid">
          {UMBRELLA_LANES.map((lane, index) => {
            const pending = activePath === lane.path;
            return (
              <article className="lane-card" key={lane.path}>
                <div className="lane-meta"><span>{String(index + 1).padStart(2, '0')}</span><span>{lane.code}</span></div>
                <h3>{lane.title}</h3>
                <p>{lane.summary}</p>
                <code>{lane.path}</code>
                <button type="button" onClick={() => runLane(lane)} disabled={Boolean(activePath)}>
                  <span>{pending ? 'Running lane' : 'Run operation'}</span>
                  <span aria-hidden="true">{pending ? '···' : '↗'}</span>
                </button>
              </article>
            );
          })}
        </div>
      </section>

      <section className="response-panel" aria-live="polite">
        <div className="response-heading">
          <span className="section-number">03</span>
          <h2>Kernel response</h2>
          <span className={`response-status ${error ? 'error' : result ? 'success' : ''}`}>
            {error ? 'REQUEST FAILED' : result ? 'NORMALIZED' : 'AWAITING OPERATION'}
          </span>
        </div>
        {error && <div className="error-message"><strong>Lane error</strong><span>{error}</span></div>}
        {result ? (
          <div className="result-grid">
            <div className="result-summary">
              <span>{result.lane.code}</span>
              <h3>{result.lane.title}</h3>
              <p>{result.response?.meta?.type || result.lane.path}</p>
            </div>
            <pre>{JSON.stringify(result.response, null, 2)}</pre>
          </div>
        ) : !error && (
          <div className="empty-state"><span>∅</span><p>Select an Umbrella lane to inspect its normalized response.</p></div>
        )}
      </section>

      <footer>
        <span>PORTAL—OS / UMBRELLA CONSOLE</span>
        <span>DETERMINISTIC · LICENSED · KERNEL AUTHORIZED</span>
      </footer>
    </main>
  );
}

export default App;
