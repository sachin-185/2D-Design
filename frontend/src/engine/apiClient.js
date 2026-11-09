// Talks to the FastAPI backend (P3's floorplan/api.py, which runs P1 + P2 + P4).
// The in-browser solver (solver.js) is kept only as an offline demo.

import { solveFloorplan } from './solver.js';
import { getBuildableArea } from './contracts.js';
import { placeWindows } from './doorsAndWindows.js';

// Vite proxies /api to http://localhost:8000 (see vite.config.js). Set VITE_API_URL to call another host.
export const DEFAULT_BACKEND_URL = import.meta.env?.VITE_API_URL || '/api';

// The engine runs several solver calls per request; P3's API stops a hung engine after 60 s.
const REQUEST_TIMEOUT_MS = 90000;
const DOOR_WIDTH = 3;
const MAIN_DOOR_SIDES = ['outside', 'exterior'];

export class ApiError extends Error {
  constructor(message, { status, errorCode, details, httpStatus } = {}) {
    super(message);
    this.status = status;          // engine status: infeasible, conflict, invalid, timeout, ...
    this.errorCode = errorCode;    // P3 error_code, e.g. INFEASIBLE_AREA
    this.details = details || {};  // e.g. details.nearest after an impossible edit
    this.httpStatus = httpStatus;
  }
}

async function postJson(url, body) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new ApiError(`The backend did not answer within ${REQUEST_TIMEOUT_MS / 1000} s.`, { status: 'timeout' });
    }
    throw new ApiError(
      'Cannot reach the backend. Start it with: python -m uvicorn floorplan.api:app --port 8000',
      { status: 'error', errorCode: 'BACKEND_UNREACHABLE' },
    );
  } finally {
    clearTimeout(timeoutId);
  }

  const text = await response.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch (e) {
    // not JSON; handled below
  }
  if (!response.ok) {
    throw toApiError(response.status, json, text);
  }
  return json;
}

function toApiError(httpStatus, json, text) {
  const detail = json?.detail;
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    // P3's error contract: {status, error_code, message, details}
    return new ApiError(detail.message || detail.error_code || 'Request failed', {
      status: detail.status, errorCode: detail.error_code, details: detail.details, httpStatus,
    });
  }
  if (Array.isArray(detail)) {
    // FastAPI 422: the request body did not match the input schema
    const lines = detail.map((d) => {
      const where = (d.loc || []).filter((p) => p !== 'body').join('.');
      const msg = String(d.msg || '').replace(/^Value error, /, '');
      return where ? `${where}: ${msg}` : msg;
    });
    return new ApiError(`Invalid input. ${lines.join('; ')}`, { status: 'invalid', errorCode: 'INVALID_INPUT', httpStatus });
  }
  return new ApiError(`Backend error ${httpStatus}: ${text || 'no details'}`, { status: 'error', httpStatus });
}

// --- backend layout -> what Canvas.jsx draws ---------------------------------------------------------

// The engine gives each door as the middle point of the wall it sits on. Canvas wants the door's start
// point and whether it lies on a vertical or horizontal wall.
function toCanvasDoor(door, boxes, index) {
  const [a, b] = door.between;
  const isMain = MAIN_DOOR_SIDES.includes(a) || MAIN_DOOR_SIDES.includes(b);
  const roomName = MAIN_DOOR_SIDES.includes(a) ? b : a;
  const box = boxes[roomName] || boxes[b];
  const onVerticalWall = box ? door.x === box.x || door.x === box.x + box.w : false;
  const half = DOOR_WIDTH / 2;
  return {
    id: `door-${index}`,
    between: isMain ? ['exterior', roomName] : [a, b],
    orientation: onVerticalWall ? 'vertical' : 'horizontal',
    x: onVerticalWall ? door.x : door.x - half,
    y: onVerticalWall ? door.y - half : door.y,
    width: DOOR_WIDTH,
    swingDir: 'in',
    isMainEntrance: isMain,
    center: { x: door.x, y: door.y },
  };
}

export function toCanvasLayout(layout, input, index) {
  const buildable = getBuildableArea(input.plot, input.setbacks || {});
  const halls = layout.hallway_segments || [];
  const boxes = {};
  for (const r of layout.rooms || []) boxes[r.name] = r;
  for (const h of halls) boxes[h.id] = h;
  const windows = layout.windows && layout.windows.length > 0
    ? layout.windows
    : placeWindows(layout.rooms || [], buildable); // the engine places no windows yet

  return {
    ...layout,
    id: `layout-${index + 1}`,
    variantNumber: index + 1,
    archetype: prettyArchetype(layout.archetype),
    hallway_segments: halls,
    doors: (layout.doors || []).map((d, i) => toCanvasDoor(d, boxes, i)),
    windows,
    problems: [],
    messages: layout.messages || [],
    // the layout exactly as the backend sent it, used as the base of the next edit
    backendLayout: layout,
  };
}

function prettyArchetype(name) {
  if (!name) return 'Free Plan';
  return name.split('_').map((w) => w[0].toUpperCase() + w.slice(1)).join(' ');
}

function toResult(json, input) {
  const layouts = (json.layouts || []).map((l, i) => toCanvasLayout(l, input, i));
  const warnings = layouts.flatMap((l) => l.messages
    .filter((m) => m.startsWith('Warning'))
    .map((m) => ({ code: 'W', message: m, rooms: [], severity: 'warning' })));
  return { success: true, layouts, problems: warnings, messages: json.messages || [], input: json.input || null };
}

// --- public calls ------------------------------------------------------------------------------------

export async function requestGenerate(inputData, useBackend = true, backendUrl = DEFAULT_BACKEND_URL) {
  if (!useBackend) {
    const result = solveFloorplan(inputData);
    if (!result.success) {
      throw new Error(result.error || 'Feasibility check failed: plot is too small.');
    }
    return { source: 'local-engine', data: result };
  }
  const json = await postJson(`${backendUrl}/generate`, inputData);
  return { source: 'backend-api', data: toResult(json, inputData) };
}

// Resize rooms in an existing layout. edits = {room: {width, height}}, lock = rooms that must not move.
// On success data.input holds the updated input (pins included) to use for the next edit.
export async function requestEdit(inputData, layout, edits, lock = [], backendUrl = DEFAULT_BACKEND_URL) {
  const base = layout.backendLayout || layout;
  const body = {
    input: inputData,
    layout: {
      score: base.score || 0,
      rooms: base.rooms.map(({ name, type, x, y, w, h }) => ({ name, type, x, y, w, h })),
      hallway_segments: (base.hallway_segments || []).map(({ id, x, y, w, h }) => ({ id, x, y, w, h })),
    },
    edits,
    lock,
  };
  const json = await postJson(`${backendUrl}/edit-layout`, body);
  return { source: 'backend-api', data: toResult(json, json.input || inputData) };
}

export async function checkBackendHealth(backendUrl = DEFAULT_BACKEND_URL) {
  try {
    const response = await fetch(`${backendUrl}/health`);
    return response.ok ? await response.json() : null;
  } catch (e) {
    return null;
  }
}
