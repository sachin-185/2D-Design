
import { solveFloorplan } from './solver.js';

export async function requestGenerate(inputData, useBackend = false, backendUrl = 'http://localhost:8000') {
  if (!useBackend) {
    const result = solveFloorplan(inputData);
    if (!result.success) {
      throw new Error(result.error || 'Feasibility check failed: plot is too small.');
    }
    return {
      source: 'local-engine',
      data: result,
    };
  }

  const isEdit = inputData.pins && inputData.pins.length > 0;
  const endpoint = isEdit ? `${backendUrl}/edit` : `${backendUrl}/generate`;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); 

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(inputData),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errText = await response.text();
      let parsedMessage = errText;
      try {
        const errJson = JSON.parse(errText);
        parsedMessage = errJson.detail || errJson.message || errText;
      } catch (e) {
      }
      throw new Error(`API Error (${response.status} from ${endpoint}): ${parsedMessage}`);
    }

    const json = await response.json();

    let layouts = [];
    if (json.layouts && Array.isArray(json.layouts)) {
      layouts = json.layouts;
    } else if (json.layout) {
      layouts = [json.layout];
    } else if (json.rooms && Array.isArray(json.rooms)) {
      layouts = [json];
    }

    layouts = layouts.map((l, idx) => ({
      ...l,
      id: l.id || `layout-${idx + 1}`,
      variantNumber: l.variantNumber || idx + 1,
      archetype: l.archetype || 'Solved Layout',
      hallway_segments: l.hallway_segments || (l.hallway ? [{ id: 'hallway_1', ...l.hallway }] : []),
      doors: l.doors || [],
      windows: l.windows || [],
      problems: l.problems || json.problems || [],
      messages: l.messages || json.messages || [],
    }));

    return {
      source: 'backend-api',
      data: {
        success: true,
        layouts,
        problems: json.problems || layouts[0]?.problems || [],
        messages: json.messages || [],
      },
    };
  } catch (err) {
    console.error('Backend API error:', err);
    throw err;
  }
}
