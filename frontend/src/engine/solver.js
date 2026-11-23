import {
  ROOM_SIZE_TABLE,
  getBuildableArea,
  checkFeasibility,
  ZONE_GRID_MAP,
} from "./contracts.js";
import { placeDoors, placeWindows } from "./doorsAndWindows.js";
import { checkLayout } from "./checker.js";

function getPointZone(cx, cy, W, L) {
  const col = Math.min(2, Math.max(0, Math.floor((cx / W) * 3)));
  const row = Math.min(2, Math.max(0, Math.floor((cy / L) * 3)));
  const zones = [
    ["SW", "S", "SE"],
    ["W", "Mid", "E"],
    ["NW", "N", "NE"],
  ];
  return zones[row][col];
}

function getZoneDistance(zoneA, zoneB) {
  const a = ZONE_GRID_MAP[zoneA];
  const b = ZONE_GRID_MAP[zoneB];
  if (!a || !b) return 0;
  return Math.abs(a.col - b.col) + Math.abs(a.row - b.row);
}

function getPhysicalEntranceSide(entrance, north = "up") {
  const mapping = {
    up: { N: "N", S: "S", E: "E", W: "W" },
    down: { N: "S", S: "N", E: "W", W: "E" },
    left: { N: "W", S: "E", E: "N", W: "S" },
    right: { N: "E", S: "W", E: "S", W: "N" },
  };
  return mapping[north]?.[entrance] || entrance;
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
      if (req.zone_mode === "must" && dist > 0) {
        score += 100 * dist;
      } else if (req.zone_mode === "try") {
        score += dist * 5;
      }
    }
  });

  const hallwayArea = (layout.hallway_segments || []).reduce(
    (acc, h) => acc + h.w * h.h,
    0,
  );
  score += Math.round(hallwayArea * 0.5);

  const living = layout.rooms.find((r) => r.type === "living");
  if (living && input.entrance) {
    const side = getPhysicalEntranceSide(input.entrance, input.north || "up");
    if (side === "S" && Math.abs(living.y) > 2) score += 15;
    if (side === "N" && Math.abs(living.y + living.h - L) > 2) score += 15;
    if (side === "E" && Math.abs(living.x + living.w - W) > 2) score += 15;
    if (side === "W" && Math.abs(living.x) > 2) score += 15;
  }

  return Math.round(score);
}

function solveCentralHallway(input, buildable, pinnedMap) {
  const W = buildable.width;
  const L = buildable.length;
  const messages = [];

  const hallwayW = Math.max(3, Math.min(4, Math.floor(W * 0.12) || 3));
  const availableW = W - hallwayW;
  let leftW = Math.floor(availableW / 2);
  if (availableW >= 20) {
    leftW = Math.min(16, Math.max(12, Math.floor(availableW * 0.55)));
  }
  const rightW = availableW - leftW;
  const hallwayX = leftW;

  const hallway_segments = [
    {
      id: "hallway_1",
      x: hallwayX,
      y: 0,
      w: hallwayW,
      h: L,
    },
  ];

  const entrance = getPhysicalEntranceSide(input.entrance || "S", input.north || "up");
  const livingReq = input.rooms.find((r) => r.type === "living") || input.rooms[0];
  const kitchenReq = input.rooms.find((r) => r.type === "kitchen");

  const leftRooms = [];
  const rightRooms = [];
  const attachedByParent = new Map();

  input.rooms.forEach((r) => {
    if (r.attached_to) {
      if (!attachedByParent.has(r.attached_to)) {
        attachedByParent.set(r.attached_to, []);
      }
      attachedByParent.get(r.attached_to).push(r);
    }
  });

  const primaryRooms = input.rooms.filter((r) => !r.attached_to);

  leftRooms.push(livingReq);
  if (kitchenReq && kitchenReq.name !== livingReq.name) {
    leftRooms.push(kitchenReq);
  }

  primaryRooms.forEach((r) => {
    if (r.name === livingReq.name) return;
    if (kitchenReq && r.name === kitchenReq.name) return;
    rightRooms.push(r);
  });

  if (rightRooms.length === 0 && leftRooms.length > 2) {
    rightRooms.push(leftRooms.pop());
  }

  const placedRooms = [];

  function placeWing(wingRooms, startX, wingWidth) {
    if (wingRooms.length === 0) return;

    const units = [];
    wingRooms.forEach((parent) => {
      const children = attachedByParent.get(parent.name) || [];
      units.push({ parent, children });
    });

    const unitCount = units.length;
    let remainingHeight = L;
    let currentY = 0;

    units.forEach((unit, uIdx) => {
      const isLastUnit = uIdx === unitCount - 1;
      const parentPin = pinnedMap[unit.parent.name];
      const parentConfig = ROOM_SIZE_TABLE[unit.parent.type] || ROOM_SIZE_TABLE.bedroom;
      const hasChildren = unit.children.length > 0;

      let unitTotalH;
      if (isLastUnit) {
        unitTotalH = remainingHeight;
      } else {
        const share = Math.round(remainingHeight / (unitCount - uIdx));
        const needed = hasChildren ? parentConfig.min.h + 7 : parentConfig.min.h;
        unitTotalH = Math.max(needed, share);
        if (remainingHeight - unitTotalH < 8 && unitCount - uIdx > 1) {
          unitTotalH = Math.max(needed, remainingHeight - 8);
        }
      }

      if (hasChildren) {
        const child = unit.children[0];
        const childPin = pinnedMap[child.name];
        const childConfig = ROOM_SIZE_TABLE[child.type] || ROOM_SIZE_TABLE.bathroom;

        let childH = childPin?.height || childConfig.preferred.h;
        childH = Math.max(childConfig.min.h, Math.min(childConfig.max.h, childH));

        let parentH = unitTotalH - childH;
        if (parentPin?.height) {
          parentH = parentPin.height;
        } else {
          parentH = Math.max(parentConfig.min.h, parentH);
        }

        const parentW = parentPin?.width ? Math.min(parentPin.width, wingWidth) : wingWidth;
        const childW = childPin?.width ? Math.min(childPin.width, wingWidth) : wingWidth;

        placedRooms.push({
          name: unit.parent.name,
          type: unit.parent.type,
          x: startX,
          y: currentY,
          w: parentW,
          h: parentH,
        });

        placedRooms.push({
          name: child.name,
          type: child.type,
          x: startX,
          y: currentY + parentH,
          w: childW,
          h: childH,
        });

        const placedUnitH = parentH + childH;
        remainingHeight -= placedUnitH;
        currentY += placedUnitH;
      } else {
        let parentH = parentPin?.height || unitTotalH;
        if (!parentPin?.height) {
          parentH = Math.max(parentConfig.min.h, Math.min(parentConfig.max.h, parentH));
          if (isLastUnit && remainingHeight > 0) {
            parentH = remainingHeight;
          }
        }

        const parentW = parentPin?.width ? Math.min(parentPin.width, wingWidth) : wingWidth;

        placedRooms.push({
          name: unit.parent.name,
          type: unit.parent.type,
          x: startX,
          y: currentY,
          w: parentW,
          h: parentH,
        });

        remainingHeight -= parentH;
        currentY += parentH;
      }
    });
  }

  placeWing(leftRooms, 0, leftW);
  placeWing(rightRooms, hallwayX + hallwayW, rightW);

  return {
    archetype: "Central Hallway",
    hallway_segments,
    rooms: placedRooms,
    messages,
  };
}

function solveSideCorridor(input, buildable, pinnedMap) {
  const W = buildable.width;
  const L = buildable.length;
  const messages = [];

  const entrance = getPhysicalEntranceSide(input.entrance || "S", input.north || "up");
  const isHorizontalCorridor = entrance === "S" || entrance === "N";
  const corridorSize = Math.max(3, Math.min(4, Math.floor((isHorizontalCorridor ? L : W) * 0.12) || 4));

  let hallway_segments = [];
  let availableX = 0;
  let availableY = 0;
  let availableW = W;
  let availableL = L;

  if (entrance === "S") {
    hallway_segments = [{ id: "hallway_1", x: 0, y: 0, w: W, h: corridorSize }];
    availableY = corridorSize;
    availableL = L - corridorSize;
  } else if (entrance === "N") {
    hallway_segments = [{ id: "hallway_1", x: 0, y: L - corridorSize, w: W, h: corridorSize }];
    availableL = L - corridorSize;
  } else if (entrance === "W") {
    hallway_segments = [{ id: "hallway_1", x: 0, y: 0, w: corridorSize, h: L }];
    availableX = corridorSize;
    availableW = W - corridorSize;
  } else {
    hallway_segments = [{ id: "hallway_1", x: W - corridorSize, y: 0, w: corridorSize, h: L }];
    availableW = W - corridorSize;
  }

  const attachedByParent = new Map();
  input.rooms.forEach((r) => {
    if (r.attached_to) {
      if (!attachedByParent.has(r.attached_to)) {
        attachedByParent.set(r.attached_to, []);
      }
      attachedByParent.get(r.attached_to).push(r);
    }
  });

  const primaryRooms = input.rooms.filter((r) => !r.attached_to);
  const units = primaryRooms.map((parent) => ({
    parent,
    children: attachedByParent.get(parent.name) || [],
  }));

  const placedRooms = [];
  const count = units.length;

  if (isHorizontalCorridor) {
    let curX = availableX;
    units.forEach((unit, idx) => {
      const isLast = idx === count - 1;
      const parentPin = pinnedMap[unit.parent.name];
      const sliceW = isLast ? availableW - (curX - availableX) : Math.floor(availableW / count);
      const roomW = parentPin?.width ? Math.min(parentPin.width, sliceW) : sliceW;

      if (unit.children.length > 0) {
        const child = unit.children[0];
        const childPin = pinnedMap[child.name];
        const childConfig = ROOM_SIZE_TABLE[child.type] || ROOM_SIZE_TABLE.bathroom;
        let childH = childPin?.height || childConfig.preferred.h;
        childH = Math.max(childConfig.min.h, Math.min(childConfig.max.h, childH));
        const parentH = availableL - childH;

        const parentY = entrance === "S" ? availableY : availableY + childH;
        const childY = entrance === "S" ? availableY + parentH : availableY;

        placedRooms.push({
          name: unit.parent.name,
          type: unit.parent.type,
          x: curX,
          y: parentY,
          w: roomW,
          h: parentPin?.height || parentH,
        });

        placedRooms.push({
          name: child.name,
          type: child.type,
          x: curX,
          y: childY,
          w: childPin?.width ? Math.min(childPin.width, roomW) : roomW,
          h: childH,
        });
      } else {
        placedRooms.push({
          name: unit.parent.name,
          type: unit.parent.type,
          x: curX,
          y: availableY,
          w: roomW,
          h: parentPin?.height || availableL,
        });
      }
      curX += sliceW;
    });
  } else {
    let curY = availableY;
    units.forEach((unit, idx) => {
      const isLast = idx === count - 1;
      const parentPin = pinnedMap[unit.parent.name];
      const sliceH = isLast ? availableL - (curY - availableY) : Math.floor(availableL / count);
      const roomH = parentPin?.height ? Math.min(parentPin.height, sliceH) : sliceH;

      if (unit.children.length > 0) {
        const child = unit.children[0];
        const childPin = pinnedMap[child.name];
        const childConfig = ROOM_SIZE_TABLE[child.type] || ROOM_SIZE_TABLE.bathroom;
        let childW = childPin?.width || childConfig.preferred.w;
        childW = Math.max(childConfig.min.w, Math.min(childConfig.max.w, childW));
        const parentW = availableW - childW;

        const parentX = entrance === "W" ? availableX : availableX + childW;
        const childX = entrance === "W" ? availableX + parentW : availableX;

        placedRooms.push({
          name: unit.parent.name,
          type: unit.parent.type,
          x: parentX,
          y: curY,
          w: parentPin?.width || parentW,
          h: roomH,
        });

        placedRooms.push({
          name: child.name,
          type: child.type,
          x: childX,
          y: curY,
          w: childW,
          h: childPin?.height ? Math.min(childPin.height, roomH) : roomH,
        });
      } else {
        placedRooms.push({
          name: unit.parent.name,
          type: unit.parent.type,
          x: availableX,
          y: curY,
          w: parentPin?.width || availableW,
          h: roomH,
        });
      }
      curY += sliceH;
    });
  }

  return {
    archetype: "Side Corridor Flow",
    hallway_segments,
    rooms: placedRooms,
    messages,
  };
}

function solveLivingHub(input, buildable, pinnedMap) {
  const W = buildable.width;
  const L = buildable.length;
  const messages = [];

  const livingReq = input.rooms.find((r) => r.type === "living") || input.rooms[0];
  const otherRooms = input.rooms.filter((r) => r.name !== livingReq.name);

  const livingConfig = ROOM_SIZE_TABLE.living;
  const minLivingH = livingConfig.min.h;
  const preferredLivingH = livingConfig.preferred.h;
  const maxAvailableLivingH = Math.max(minLivingH, L - 10);
  const targetLivingH = Math.min(maxAvailableLivingH, Math.max(minLivingH, Math.floor(L * 0.42) || preferredLivingH));

  const entrance = getPhysicalEntranceSide(input.entrance || "S", input.north || "up");
  const livingY = entrance === "S" ? 0 : L - targetLivingH;
  const otherY = entrance === "S" ? targetLivingH : 0;
  const otherH = L - targetLivingH;

  const placedRooms = [];
  const livingPin = pinnedMap[livingReq.name];

  placedRooms.push({
    name: livingReq.name,
    type: livingReq.type,
    x: 0,
    y: livingY,
    w: livingPin?.width || W,
    h: livingPin?.height || targetLivingH,
  });

  const hallwayW = Math.max(3, Math.min(4, Math.floor(W * 0.12) || 4));
  const leftWingW = Math.floor((W - hallwayW) / 2);
  const rightWingW = W - hallwayW - leftWingW;
  const hallwayX = leftWingW;

  const hallway_segments = [
    {
      id: "hallway_1",
      x: hallwayX,
      y: otherY,
      w: hallwayW,
      h: otherH,
    },
  ];

  const leftRooms = [];
  const rightRooms = [];
  const attachedByParent = new Map();

  otherRooms.forEach((r) => {
    if (r.attached_to) {
      if (!attachedByParent.has(r.attached_to)) {
        attachedByParent.set(r.attached_to, []);
      }
      attachedByParent.get(r.attached_to).push(r);
    }
  });

  const primaryOthers = otherRooms.filter((r) => !r.attached_to);

  primaryOthers.forEach((r) => {
    if (r.zone && (r.zone.includes("W") || r.zone === "NW" || r.zone === "SW")) {
      leftRooms.push(r);
    } else if (r.zone && (r.zone.includes("E") || r.zone === "NE" || r.zone === "SE")) {
      rightRooms.push(r);
    } else {
      if (leftRooms.length <= rightRooms.length) {
        leftRooms.push(r);
      } else {
        rightRooms.push(r);
      }
    }
  });

  function placeHubWing(wingRooms, startX, wingWidth) {
    if (wingRooms.length === 0) return;

    const units = wingRooms.map((parent) => ({
      parent,
      children: attachedByParent.get(parent.name) || [],
    }));

    const unitCount = units.length;
    let remainingHeight = otherH;
    let currentY = otherY;

    units.forEach((unit, idx) => {
      const isLast = idx === unitCount - 1;
      const parentPin = pinnedMap[unit.parent.name];
      const parentConfig = ROOM_SIZE_TABLE[unit.parent.type] || ROOM_SIZE_TABLE.bedroom;
      const hasChildren = unit.children.length > 0;

      let unitTotalH;
      if (isLast) {
        unitTotalH = remainingHeight;
      } else {
        const share = Math.round(remainingHeight / (unitCount - idx));
        const needed = hasChildren ? parentConfig.min.h + 7 : parentConfig.min.h;
        unitTotalH = Math.max(needed, share);
      }

      if (hasChildren) {
        const child = unit.children[0];
        const childPin = pinnedMap[child.name];
        const childConfig = ROOM_SIZE_TABLE[child.type] || ROOM_SIZE_TABLE.bathroom;

        let childH = childPin?.height || childConfig.preferred.h;
        childH = Math.max(childConfig.min.h, Math.min(childConfig.max.h, childH));
        const parentH = unitTotalH - childH;

        placedRooms.push({
          name: unit.parent.name,
          type: unit.parent.type,
          x: startX,
          y: currentY,
          w: parentPin?.width ? Math.min(parentPin.width, wingWidth) : wingWidth,
          h: parentPin?.height || parentH,
        });

        placedRooms.push({
          name: child.name,
          type: child.type,
          x: startX,
          y: currentY + parentH,
          w: childPin?.width ? Math.min(childPin.width, wingWidth) : wingWidth,
          h: childH,
        });

        const placedUnitH = parentH + childH;
        remainingHeight -= placedUnitH;
        currentY += placedUnitH;
      } else {
        let parentH = parentPin?.height || unitTotalH;
        if (!parentPin?.height && isLast && remainingHeight > 0) {
          parentH = remainingHeight;
        }

        placedRooms.push({
          name: unit.parent.name,
          type: unit.parent.type,
          x: startX,
          y: currentY,
          w: parentPin?.width ? Math.min(parentPin.width, wingWidth) : wingWidth,
          h: parentH,
        });

        remainingHeight -= parentH;
        currentY += parentH;
      }
    });
  }

  placeHubWing(leftRooms, 0, leftWingW);
  placeHubWing(rightRooms, hallwayX + hallwayW, rightWingW);

  return {
    archetype: "Living Hub & Direct Wings",
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
      hasValidLayout: false,
      error: feasibility.message,
      feasibility,
      layouts: [],
      problems: [
        {
          code: "I1",
          message: `Feasibility Check Failed: Plot shortfall of ${feasibility.shortfall} sq ft. Total required: ${feasibility.totalRequired} sq ft vs buildable: ${feasibility.buildableArea} sq ft.`,
          rooms: [],
          severity: "error",
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
      getPhysicalEntranceSide(input.entrance || "S", input.north || "up"),
      buildable,
      input.rooms,
    );
    const windows = placeWindows(layout.rooms, buildable);
    const score = scoreLayout(layout, input);

    const problems = checkLayout(layout, input, doors);

    unconnectedRooms.forEach((u) => {
      problems.push({
        code: "F1",
        message: u.reason,
        rooms: [u.room],
        severity: "error",
      });
    });

    const errorCount = problems.filter((p) => p.severity === "error").length;
    const warningCount = problems.filter((p) => p.severity === "warning").length;
    const isValid = errorCount === 0;

    return {
      id: `layout-${index + 1}`,
      variantNumber: index + 1,
      archetype: layout.archetype,
      score,
      isValid,
      errorCount,
      warningCount,
      rooms: layout.rooms,
      hallway_segments: layout.hallway_segments,
      hallway: layout.hallway_segments?.[0] || null,
      doors,
      windows,
      problems,
      messages: layout.messages || [],
    };
  });

  processedLayouts.sort((a, b) => {
    if (a.isValid && !b.isValid) return -1;
    if (!a.isValid && b.isValid) return 1;
    if (a.errorCount !== b.errorCount) return a.errorCount - b.errorCount;
    return a.score - b.score;
  });

  const hasValidLayout = processedLayouts.some((l) => l.isValid);

  return {
    success: true,
    hasValidLayout,
    layouts: processedLayouts,
    feasibility,
    problems: processedLayouts[0]?.problems || [],
    messages: [],
    timestamp: new Date().toISOString(),
  };
}
