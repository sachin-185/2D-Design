

import { ROOM_SIZE_TABLE, getBuildableArea, checkFeasibility, ZONE_GRID_MAP } from './contracts.js';
import { placeDoors, placeWindows } from './doorsAndWindows.js';
import { checkLayout } from './checker.js';


function getPointZone(cx, cy, W, L) {
  const col = Math.min(2, Math.max(0, Math.floor((cx / W) * 3)));
  const row = Math.min(2, Math.max(0, Math.floor((cy / L) * 3)));
  const zones = [
    ['SW', 'S', 'SE'],
    ['W', 'Mid', 'E'],
    ['NW', 'N', 'NE'],
  ];
  return zones[row][col];
}

function getZoneDistance(zoneA, zoneB) {
  const a = ZONE_GRID_MAP[zoneA];
  const b = ZONE_GRID_MAP[zoneB];
  if (!a || !b) return 0;
  return Math.abs(a.col - b.col) + Math.abs(a.row - b.row);
}

export function scoreLayout(layout, input) {
  let score = 0;
  const buildable = getBuildableArea(input.plot, input.setbacks);
  const W = buildable.width;
  const L = buildable.length;

  layout.rooms.forEach((room) => {
    const config = ROOM_SIZE_TABLE[room.type] || ROOM_SIZE_TABLE.living;
    const prefW = config.preferred.w;
    const prefH = config.preferred.h;
    score += Math.abs(room.w - prefW) * 2;
    score += Math.abs(room.h - prefH) * 2;

    const req = input.rooms.find((r) => r.name === room.name);
    if (req && req.zone) {
      const cx = room.x + room.w / 2;
      const cy = room.y + room.h / 2;
      const actualZone = getPointZone(cx, cy, W, L);
      const dist = getZoneDistance(req.zone, actualZone);
      if (req.zone_mode === 'must' && dist > 0) {
        score += 100 * dist;
      } else if (req.zone_mode === 'try') {
        score += dist * 5;
      }
    }
  });

  const hallwayArea = (layout.hallway_segments || []).reduce((acc, h) => acc + h.w * h.h, 0);
  score += Math.round(hallwayArea * 0.5);

  const living = layout.rooms.find((r) => r.type === 'living');
  if (living && input.entrance) {
    const side = input.entrance;
    if (side === 'S' && Math.abs(living.y) > 2) score += 15;
    if (side === 'N' && Math.abs(living.y + living.h - L) > 2) score += 15;
    if (side === 'E' && Math.abs(living.x + living.w - W) > 2) score += 15;
    if (side === 'W' && Math.abs(living.x) > 2) score += 15;
  }

  return Math.round(score);
}


function solveCentralHallway(input, buildable, pinnedMap) {
  const W = buildable.width;
  const L = buildable.length;
  const messages = [];

  const hallwayW = Math.max(3, Math.min(5, Math.floor(W * 0.15)));
  const leftW = Math.floor((W - hallwayW) / 2);
  const rightW = W - hallwayW - leftW;
  const hallwayX = leftW;

  const hallway_segments = [
    {
      id: 'hallway_1',
      x: hallwayX,
      y: 0,
      w: hallwayW,
      h: L,
    },
  ];

  const reqRooms = [...input.rooms];
  const leftRooms = [];
  const rightRooms = [];

  const unattached = reqRooms.filter(r => !r.attached_to);
  const attached = reqRooms.filter(r => r.attached_to);

  unattached.forEach((r) => {
    if (r.zone && (r.zone.includes('W') || r.zone === 'NW' || r.zone === 'SW')) {
      leftRooms.push(r);
    } else if (r.zone && (r.zone.includes('E') || r.zone === 'NE' || r.zone === 'SE')) {
      rightRooms.push(r);
    } else {
      if (leftRooms.length <= rightRooms.length) leftRooms.push(r);
      else rightRooms.push(r);
    }
  });

  attached.forEach((r) => {
    const lIdx = leftRooms.findIndex(x => x.name === r.attached_to);
    if (lIdx >= 0) {
      leftRooms.splice(lIdx + 1, 0, r);
    } else {
      const rIdx = rightRooms.findIndex(x => x.name === r.attached_to);
      if (rIdx >= 0) {
        rightRooms.splice(rIdx + 1, 0, r);
      } else {
        leftRooms.push(r);
      }
    }
  });

  if (leftRooms.length === 0 && rightRooms.length > 1) {
    leftRooms.push(rightRooms.shift());
  } else if (rightRooms.length === 0 && leftRooms.length > 1) {
    rightRooms.push(leftRooms.shift());
  }

  const placedRooms = [];

  function placeWing(wingRooms, startX, wingWidth) {
    const count = wingRooms.length;
    if (count === 0) return;

    let remainingHeight = L;
    let currentY = 0; 

    wingRooms.forEach((r, idx) => {
      const pin = pinnedMap[r.name];
      const isLast = idx === count - 1;
      let roomH;

      if (isLast) {
        roomH = remainingHeight;
      } else {
        const config = ROOM_SIZE_TABLE[r.type] || ROOM_SIZE_TABLE.bedroom;
        const targetPrefH = config.preferred.h;
        const share = Math.round(remainingHeight / (count - idx));
        roomH = Math.max(config.min.h, Math.min(config.max.h, share || targetPrefH));
        if (remainingHeight - roomH < 7) {
          roomH = Math.max(7, remainingHeight - 7);
        }
      }

      let roomW = wingWidth;
      if (pin?.width) {
        roomW = pin.width;
      }

      placedRooms.push({
        name: r.name,
        type: r.type,
        x: startX,
        y: currentY,
        w: roomW,
        h: pin?.height || roomH,
      });

      remainingHeight -= roomH;
      currentY += roomH;
    });
  }

  placeWing(leftRooms, 0, leftW);
  placeWing(rightRooms, hallwayX + hallwayW, rightW);

  return {
    archetype: 'Central Hallway',
    hallway_segments,
    rooms: placedRooms,
    messages,
  };
}


function solveSideCorridor(input, buildable, pinnedMap) {
  const W = buildable.width;
  const L = buildable.length;
  const messages = [];

  const entrance = input.entrance || 'S';
  const corridorH = 4;
  const corridorY = entrance === 'S' ? 0 : L - corridorH;

  const hallway_segments = [
    {
      id: 'hallway_1',
      x: 0,
      y: corridorY,
      w: W,
      h: corridorH,
    },
  ];

  const remainingL = L - corridorH;
  const startY = entrance === 'S' ? corridorH : 0;

  const reqRooms = [...input.rooms];
  const placedRooms = [];

  if (reqRooms.length <= 4) {
    const midX = Math.floor(W / 2);
    const midY = Math.floor(remainingL / 2);

    const positions = [
      { x: 0, y: startY, w: midX, h: midY },
      { x: midX, y: startY, w: W - midX, h: midY },
      { x: 0, y: startY + midY, w: midX, h: remainingL - midY },
      { x: midX, y: startY + midY, w: W - midX, h: remainingL - midY },
    ];

    reqRooms.forEach((r, idx) => {
      const pos = positions[idx] || positions[0];
      const pin = pinnedMap[r.name];
      placedRooms.push({
        name: r.name,
        type: r.type,
        x: pos.x,
        y: pos.y,
        w: pin?.width || pos.w,
        h: pin?.height || pos.h,
      });
    });
  } else {
    const count = reqRooms.length;
    let curX = 0;
    reqRooms.forEach((r, idx) => {
      const isLast = idx === count - 1;
      const sliceW = isLast ? W - curX : Math.floor(W / count);
      const pin = pinnedMap[r.name];
      placedRooms.push({
        name: r.name,
        type: r.type,
        x: curX,
        y: startY,
        w: pin?.width || sliceW,
        h: pin?.height || remainingL,
      });
      curX += sliceW;
    });
  }

  return {
    archetype: 'Side Corridor Flow',
    hallway_segments,
    rooms: placedRooms,
    messages,
  };
}


function solveLivingHub(input, buildable, pinnedMap) {
  const W = buildable.width;
  const L = buildable.length;
  const messages = [];

  const livingReq = input.rooms.find((r) => r.type === 'living') || input.rooms[0];
  const otherRooms = input.rooms.filter((r) => r.name !== livingReq.name);

  const livingH = Math.max(12, Math.floor(L * 0.45));
  const entrance = input.entrance || 'S';
  const livingY = entrance === 'S' ? 0 : L - livingH;
  const otherY = entrance === 'S' ? livingH : 0;
  const otherH = L - livingH;

  const placedRooms = [];
  const livingPin = pinnedMap[livingReq.name];

  placedRooms.push({
    name: livingReq.name,
    type: livingReq.type,
    x: 0,
    y: livingY,
    w: livingPin?.width || W,
    h: livingPin?.height || livingH,
  });

  const count = otherRooms.length;
  let curX = 0;

  otherRooms.forEach((r, idx) => {
    const isLast = idx === count - 1;
    const pin = pinnedMap[r.name];
    let roomW = isLast ? W - curX : Math.floor(W / count);

    if (pin?.width) {
      roomW = pin.width;
    }

    placedRooms.push({
      name: r.name,
      type: r.type,
      x: curX,
      y: otherY,
      w: roomW,
      h: pin?.height || otherH,
    });

    curX += roomW;
  });

  const hallway_segments = count > 3 ? [
    {
      id: 'hallway_1',
      x: Math.floor(W * 0.35),
      y: otherY,
      w: Math.max(3, Math.floor(W * 0.3)),
      h: 3,
    },
  ] : [];

  return {
    archetype: 'Living Hub & Direct Wings',
    hallway_segments,
    rooms: placedRooms,
    messages,
  };
}


export function solveFloorplan(input) {
  const feasibility = checkFeasibility(input.plot, input.setbacks, input.rooms);

  if (!feasibility.feasible) {
    return {
      success: false,
      error: feasibility.message,
      feasibility,
      layouts: [],
      problems: [
        {
          code: 'I1',
          message: `Feasibility Check Failed: Plot shortfall of ${feasibility.shortfall} sq ft. Total required: ${feasibility.totalRequired} sq ft vs buildable: ${feasibility.buildableArea} sq ft.`,
          rooms: [],
          severity: 'error',
        },
      ],
      messages: [feasibility.message],
      timestamp: new Date().toISOString(),
    };
  }

  const buildable = getBuildableArea(input.plot, input.setbacks);

  const pinnedMap = {};
  if (input.pins && Array.isArray(input.pins)) {
    input.pins.forEach((p) => {
      pinnedMap[p.room] = p;
    });
  }

  const rawVariants = [
    solveCentralHallway(input, buildable, pinnedMap),
    solveLivingHub(input, buildable, pinnedMap),
    solveSideCorridor(input, buildable, pinnedMap),
  ];

  const processedLayouts = rawVariants.map((layout, index) => {
    const { doors, unconnectedRooms } = placeDoors(
      layout.rooms,
      layout.hallway_segments,
      input.entrance || 'S',
      buildable,
      input.rooms
    );
    const windows = placeWindows(layout.rooms, buildable);
    const score = scoreLayout(layout, input);

    const problems = checkLayout(layout, input, doors);

    unconnectedRooms.forEach((u) => {
      problems.push({
        code: 'F1',
        message: u.reason,
        rooms: [u.room],
        severity: 'error',
      });
    });

    return {
      id: `layout-${index + 1}`,
      variantNumber: index + 1,
      archetype: layout.archetype,
      score,
      rooms: layout.rooms,
      hallway_segments: layout.hallway_segments,
      hallway: layout.hallway_segments?.[0] || null, 
      doors,
      windows,
      problems,
      messages: layout.messages || [],
    };
  });

  processedLayouts.sort((a, b) => a.score - b.score);

  return {
    success: true,
    layouts: processedLayouts,
    feasibility,
    problems: processedLayouts[0]?.problems || [],
    messages: [],
    timestamp: new Date().toISOString(),
  };
}
