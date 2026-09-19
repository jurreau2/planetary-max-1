import { describe, expect, it } from 'vitest';

import app, { extractLaneData } from '../src/index';

type KernelEnvelope = {
  id: string;
  type: string;
  identity: string;
  payload: Record<string, unknown>;
};

function successResponse(envelope: KernelEnvelope): Response {
  return Response.json({
    ok: true,
    messageId: envelope.id,
    type: envelope.type,
    identity: { id: envelope.identity, roles: ['operator'] },
    route: ['orchestration'],
    result: {
      lanes: [{
        lane: 'orchestration',
        result: {
          results: [{ result: { data: { operation: envelope.type, payload: envelope.payload } } }],
        },
      }],
    },
  });
}

function bindings(handler: (envelope: KernelEnvelope) => Response | Promise<Response>) {
  return {
    KERNEL_SERVICE: {
      async fetch(request: Request): Promise<Response> {
        return handler(await request.json<KernelEnvelope>());
      },
    },
  };
}

describe('normalized Worker integration routes', () => {
  it('exposes the public edge health contract', async () => {
    const response = await app.request('/health');

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: 'ok', service: 'portal-os-worker' });
  });

  it.each([
    ['GET', '/api/autonomy', 'autonomy.state'],
    ['GET', '/universe/state', 'universe.state'],
    ['GET', '/universe/umbrella', 'universe.umbrella'],
    ['POST', '/universe/tick', 'universe.tick'],
    ['POST', '/umbrella/identity/license', 'identity.physics.license'],
    ['POST', '/umbrella/governance/license', 'governance.engine.license'],
    ['POST', '/umbrella/apex/advisory', 'apex.alignment.advisory'],
    ['POST', '/umbrella/sim/pack', 'umbrella.sim.pack'],
  ])('normalizes %s %s lane data', async (method, path, type) => {
    let forwarded: KernelEnvelope | undefined;
    const response = await app.request(path, {
      method,
      headers: {
        Authorization: 'Bearer shared-service-token',
        ...(method === 'POST' ? { 'Content-Type': 'application/json' } : {}),
      },
      body: method === 'POST' ? JSON.stringify({ changes: { population: 1 } }) : undefined,
    }, bindings((envelope) => {
      forwarded = envelope;
      return successResponse(envelope);
    }));

    expect(response.status).toBe(200);
    expect(forwarded).toMatchObject({ type, identity: 'shared-service-token' });
    expect(await response.json()).toEqual({
      ok: true,
      data: { operation: type, payload: method === 'POST' ? { changes: { population: 1 } } : {} },
      meta: {
        messageId: forwarded?.id,
        type,
        identity: { id: 'shared-service-token', roles: ['operator'] },
        route: ['orchestration'],
      },
    });
  });

  it('rejects a missing bearer token before calling the kernel', async () => {
    let called = false;
    const response = await app.request('/universe/state', {}, bindings(() => {
      called = true;
      return Response.json({ ok: true });
    }));

    expect(response.status).toBe(401);
    expect(called).toBe(false);
    expect(await response.json()).toEqual({
      ok: false,
      error: { code: 'UNAUTHENTICATED', message: 'Bearer token required' },
    });
  });

  it('preserves a kernel rejection for an invalid bearer token', async () => {
    const response = await app.request('/api/autonomy', {
      headers: { Authorization: 'Bearer not-registered' },
    }, bindings(() => Response.json({
      ok: false,
      messageId: 'rejected-1',
      error: { code: 'UNAUTHENTICATED', message: 'invalid identity token' },
    }, { status: 401 })));

    expect(response.status).toBe(401);
    expect(await response.json()).toMatchObject({
      ok: false,
      error: { code: 'UNAUTHENTICATED', message: 'invalid identity token' },
    });
  });

  it('preserves observer denial details for universe tick', async () => {
    const response = await app.request('/universe/tick', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer observer-token',
        'Content-Type': 'application/json',
      },
      body: '{}',
    }, bindings(() => Response.json({
      ok: false,
      messageId: 'denied-1',
      error: { code: 'FORBIDDEN', message: 'not authorized for universe.tick' },
    }, { status: 403 })));

    expect(response.status).toBe(403);
    expect(await response.json()).toMatchObject({
      ok: false,
      error: { code: 'FORBIDDEN', message: 'not authorized for universe.tick' },
    });
  });

  it('forwards an over-tier request unchanged and normalizes the kernel cap', async () => {
    const response = await app.request('/umbrella/identity/license', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer basic-license-token',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ tier: 'enterprise', input: { subject: 'alpha' } }),
    }, bindings((envelope) => {
      expect(envelope.identity).toBe('basic-license-token');
      expect(envelope.payload).toEqual({ tier: 'enterprise', input: { subject: 'alpha' } });
      return Response.json({
        ok: true,
        messageId: envelope.id,
        type: envelope.type,
        identity: { id: 'licensed-observer', roles: ['observer'] },
        route: ['orchestration'],
        result: {
          lanes: [{
            result: {
              results: [{ result: { data: {
                tier: 'basic',
                requestedTier: 'enterprise',
                authorizedTier: 'basic',
                tierCapped: true,
                identitySignature: 'idp_v1_example',
              } } }],
            },
          }],
        },
      });
    }));

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      ok: true,
      data: {
        tier: 'basic',
        requestedTier: 'enterprise',
        authorizedTier: 'basic',
        tierCapped: true,
      },
      meta: { type: 'identity.physics.license', route: ['orchestration'] },
    });
  });

  it('rejects malformed license payloads before calling the kernel', async () => {
    let called = false;
    const response = await app.request('/umbrella/governance/license', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer professional-license-token',
        'Content-Type': 'application/json',
      },
      body: '[]',
    }, bindings(() => {
      called = true;
      return Response.json({ ok: true });
    }));

    expect(response.status).toBe(400);
    expect(called).toBe(false);
    expect(await response.json()).toEqual({
      ok: false,
      error: { code: 'INVALID_JSON', message: 'Umbrella payload must be an object' },
    });
  });
});

describe('extractLaneData', () => {
  it('extracts the nested TEC lane payload', () => {
    expect(extractLaneData({
      result: { lanes: [{ result: { results: [{ result: { data: { tick: 7 } } }] } }] },
    })).toEqual({ tick: 7 });
  });

  it('returns an empty object for a malformed kernel envelope', () => {
    expect(extractLaneData({ result: { lanes: [] } })).toEqual({});
  });
});
