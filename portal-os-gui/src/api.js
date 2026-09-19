// ============================================================
// Portal‑OS GUI — Umbrella API Binding (Final, Complete)
// ============================================================

// Bind GUI → Worker API using Vite environment variables.
// Trailing slash is removed for safety.
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.API_BASE_URL ||
  ''
).replace(/\/$/, '');

// All 8 Umbrella lanes (SET 1–4)
export const UMBRELLA_LANES = [
  {
    path: '/umbrella/identity/license',
    code: 'ID',
    title: 'Identity Physics',
    summary: 'Resolve identity signatures and stability curvature.',
  },
  {
    path: '/umbrella/governance/license',
    code: 'GV',
    title: 'Governance Engine',
    summary: 'Inspect structures, alignment, and collapse vectors.',
  },
  {
    path: '/umbrella/apex/advisory',
    code: 'AP',
    title: 'Apex Advisory',
    summary: 'Generate deterministic apex alignment guidance.',
  },
  {
    path: '/umbrella/sim/pack',
    code: 'SM',
    title: 'SIM Pack',
    summary: 'Compose licensed simulation products into one pack.',
  },
  {
    path: '/umbrella/market/forecast',
    code: 'MK',
    title: 'Market Forecast',
    summary: 'Project trends, volatility, and market risk.',
  },
  {
    path: '/umbrella/identity/mirror',
    code: 'MR',
    title: 'Identity Mirror',
    summary: 'Mirror behavior and structural identity truth.',
  },
  {
    path: '/umbrella/crossworld/access',
    code: 'CW',
    title: 'Crossworld Access',
    summary: 'Map licensed traversal across reachable worlds.',
  },
  {
    path: '/umbrella/structural/truth/license',
    code: 'ST',
    title: 'Structural Truth',
    summary: 'License structural evidence and contradiction vectors.',
  },
];

// ============================================================
// Umbrella Lane Caller
// ============================================================

export async function callUmbrellaLane(path, body, bearerToken) {
  if (!API_BASE_URL) {
    throw new Error(
      'API base URL is not configured. Set VITE_API_BASE_URL or API_BASE_URL.'
    );
  }

  if (!bearerToken || !bearerToken.trim()) {
    throw new Error('Enter a bearer token before running an Umbrella lane.');
  }

  // Timeout protection
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15_000);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${bearerToken.trim()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json')
      ? await response.json()
      : {
          ok: false,
          error: {
            code: 'INVALID_RESPONSE',
            message: await response.text(),
          },
        };

    // Umbrella normalization: payload.ok === false → error
    if (!response.ok || payload?.ok === false) {
      const code = payload?.error?.code || `HTTP_${response.status}`;
      const message =
        payload?.error?.message ||
        response.statusText ||
        'Umbrella request failed';

      const error = new Error(`${code}: ${message}`);
      error.payload = payload;
      throw error;
    }

    return payload;
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error('The Worker did not respond within 15 seconds.');
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}
