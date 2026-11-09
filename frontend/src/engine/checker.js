

import { ROOM_SIZE_TABLE, getBuildableArea } from './contracts.js';

export function checkLayout(layout, input, doors = []) {
  const problems = [];
  const buildable = getBuildableArea(input.plot, input.setbacks);
  const W = buildable.width;
  const L = buildable.length;

  const rooms = layout?.rooms || [];
  const hallwaySegments = layout?.hallway_segments || (layout?.hallway ? [{ id: 'hallway_1', ...layout.hallway }] : []);
  const allDoors = doors.length > 0 ? doors : (layout?.doors || []);

  const roomMap = new Map();
  rooms.forEach((r) => roomMap.set(r.name, r));

  if (!input.rooms || input.rooms.length === 0) {
    problems.push({
      code: 'I1',
      message: 'No rooms requested in input.',
      rooms: [],
      severity: 'error',
    });
  }
  if (input.rooms && input.rooms.length > 10) {
    problems.push({
      code: 'I1',
      message: `Room count (${input.rooms.length}) exceeds the maximum limit of 10 rooms.`,
      rooms: input.rooms.map((r) => r.name),
      severity: 'error',
    });
  }
  input.rooms?.forEach((r) => {
    if (!ROOM_SIZE_TABLE[r.type]) {
      problems.push({
        code: 'I1',
        message: `Invalid room type '${r.type}' for room '${r.name}'. Allowed types: living, kitchen, bedroom, bathroom, dining, study, utility, store, storage, laundry.`,
        rooms: [r.name],
        severity: 'error',
      });
    }
  });

  rooms.forEach((r) => {
    if (r.x < 0 || r.y < 0 || r.x + r.w > W || r.y + r.h > L) {
      problems.push({
        code: 'H1',
        message: `Room '${r.name}' exceeds buildable area bounds (${W}x${L} ft): placed at (${r.x}, ${r.y}, ${r.w}x${r.h}).`,
        rooms: [r.name],
        severity: 'error',
      });
    }
  });

  hallwaySegments.forEach((seg) => {
    if (seg.x < 0 || seg.y < 0 || seg.x + seg.w > W || seg.y + seg.h > L) {
      problems.push({
        code: 'H1',
        message: `Hallway segment '${seg.id || 'hallway'}' exceeds buildable area bounds (${W}x${L} ft).`,
        rooms: [],
        severity: 'error',
      });
    }
  });

  rooms.forEach((r) => {
    const config = ROOM_SIZE_TABLE[r.type];
    if (config) {
      if (r.w < config.min.w || r.h < config.min.h) {
        problems.push({
          code: 'H2',
          message: `Room '${r.name}' (${r.w}x${r.h} ft) is below minimum allowed size (${config.min.w}x${config.min.h} ft).`,
          rooms: [r.name],
          severity: 'error',
        });
      }
      if (r.w > config.max.w || r.h > config.max.h) {
        problems.push({
          code: 'H2',
          message: `Room '${r.name}' (${r.w}x${r.h} ft) exceeds maximum allowed size (${config.max.w}x${config.max.h} ft).`,
          rooms: [r.name],
          severity: 'error',
        });
      }
    }
  });

  for (let i = 0; i < rooms.length; i++) {
    for (let j = i + 1; j < rooms.length; j++) {
      const a = rooms[i];
      const b = rooms[j];
      const overlapX = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
      const overlapY = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
      if (overlapX > 0 && overlapY > 0) {
        problems.push({
          code: 'H3',
          message: `Rooms '${a.name}' and '${b.name}' overlap by ${overlapX}x${overlapY} ft.`,
          rooms: [a.name, b.name],
          severity: 'error',
        });
      }
    }
  }

  rooms.forEach((r) => {
    hallwaySegments.forEach((seg) => {
      const overlapX = Math.max(0, Math.min(r.x + r.w, seg.x + seg.w) - Math.max(r.x, seg.x));
      const overlapY = Math.max(0, Math.min(r.y + r.h, seg.y + seg.h) - Math.max(r.y, seg.y));
      if (overlapX > 0 && overlapY > 0) {
        problems.push({
          code: 'H3',
          message: `Room '${r.name}' overlaps with hallway segment '${seg.id || 'hallway'}' by ${overlapX}x${overlapY} ft.`,
          rooms: [r.name],
          severity: 'error',
        });
      }
    });
  });

  let totalRoomArea = rooms.reduce((sum, r) => sum + r.w * r.h, 0);
  let totalHallwayArea = hallwaySegments.reduce((sum, h) => sum + h.w * h.h, 0);
  let totalCovered = totalRoomArea + totalHallwayArea;
  if (totalCovered < buildable.area) {
    const unallocated = buildable.area - totalCovered;
    const pct = Math.round((totalCovered / buildable.area) * 100);
    problems.push({
      code: 'H4',
      message: `Partial plot coverage: ${unallocated} sq ft unallocated (${pct}% covered).`,
      rooms: [],
      severity: 'warning',
    });
  } else if (totalCovered > buildable.area) {
    problems.push({
      code: 'H4',
      message: `Total room area (${totalCovered} sq ft) exceeds buildable area (${buildable.area} sq ft).`,
      rooms: [],
      severity: 'error',
    });
  }

  input.rooms?.forEach((req) => {
    if (req.type === 'bathroom' && req.attached_to) {
      const bath = roomMap.get(req.name);
      const bed = roomMap.get(req.attached_to);
      if (bath && bed) {
        const sharesWall = (
          (bath.x + bath.w === bed.x || bed.x + bed.w === bath.x) &&
          Math.min(bath.y + bath.h, bed.y + bed.h) - Math.max(bath.y, bed.y) >= 3
        ) || (
          (bath.y + bath.h === bed.y || bed.y + bed.h === bath.y) &&
          Math.min(bath.x + bath.w, bed.x + bed.w) - Math.max(bath.x, bed.x) >= 3
        );
        if (!sharesWall) {
          problems.push({
            code: 'H6',
            message: `Attached bathroom '${bath.name}' does not share a min 3ft wall with '${bed.name}'.`,
            rooms: [bath.name, bed.name],
            severity: 'error',
          });
        }
      }
    }
  });

  const livingRooms = rooms.filter((r) => r.type === 'living');
  const kitchen = rooms.find((r) => r.type === 'kitchen');
  if (kitchen && livingRooms.length > 0) {
    const firstLiving = livingRooms[0];
    const sharesWallLiving = (
      (kitchen.x + kitchen.w === firstLiving.x || firstLiving.x + firstLiving.w === kitchen.x) &&
      Math.min(kitchen.y + kitchen.h, firstLiving.y + firstLiving.h) - Math.max(kitchen.y, firstLiving.y) >= 3
    ) || (
      (kitchen.y + kitchen.h === firstLiving.y || firstLiving.y + firstLiving.h === kitchen.y) &&
      Math.min(kitchen.x + kitchen.w, firstLiving.x + firstLiving.w) - Math.max(kitchen.x, firstLiving.x) >= 3
    );
    const sharesHallway = hallwaySegments.some((h) => (
      ((kitchen.x + kitchen.w === h.x || h.x + h.w === kitchen.x) &&
       Math.min(kitchen.y + kitchen.h, h.y + h.h) - Math.max(kitchen.y, h.y) >= 3) ||
      ((kitchen.y + kitchen.h === h.y || h.y + h.h === kitchen.y) &&
       Math.min(kitchen.x + kitchen.w, h.x + h.w) - Math.max(kitchen.x, h.x) >= 3)
    ));
    if (!sharesWallLiving && !sharesHallway) {
      problems.push({
        code: 'H6',
        message: `Kitchen '${kitchen.name}' does not share a wall with living room '${firstLiving.name}' or hallway.`,
        rooms: [kitchen.name, firstLiving.name],
        severity: 'warning',
      });
    }
  }

  hallwaySegments.forEach((seg) => {
    if (seg.w < 3 && seg.h < 3) {
      problems.push({
        code: 'HW1',
        message: `Hallway segment '${seg.id || 'hallway'}' width is less than 3 ft minimum.`,
        rooms: [],
        severity: 'error',
      });
    }
  });

  if (hallwaySegments.length > 1) {
    for (let i = 1; i < hallwaySegments.length; i++) {
      const segA = hallwaySegments[i - 1];
      const segB = hallwaySegments[i];
      const connected = (
        (segA.x + segA.w === segB.x || segB.x + segB.w === segA.x) &&
        Math.min(segA.y + segA.h, segB.y + segB.h) > Math.max(segA.y, segB.y)
      ) || (
        (segA.y + segA.h === segB.y || segB.y + segB.h === segA.y) &&
        Math.min(segA.x + segA.w, segB.x + segB.w) > Math.max(segA.x, segB.x)
      );
      if (!connected) {
        problems.push({
          code: 'HW2',
          message: `Disjoint hallway segments '${segA.id}' and '${segB.id}'.`,
          rooms: [],
          severity: 'warning',
        });
      }
    }
  }

  const entrance = input.entrance || 'S';
  const mainDoor = allDoors.find((d) => d.isMainEntrance);
  if (mainDoor) {
    let matchesSide = false;
    if (entrance === 'S' && Math.abs(mainDoor.y) < 0.1) matchesSide = true;
    if (entrance === 'N' && Math.abs(mainDoor.y - L) < 0.1) matchesSide = true;
    if (entrance === 'W' && Math.abs(mainDoor.x) < 0.1) matchesSide = true;
    if (entrance === 'E' && Math.abs(mainDoor.x - W) < 0.1) matchesSide = true;
    if (!matchesSide) {
      problems.push({
        code: 'E1',
        message: `Main entrance door is not on requested entrance side (${entrance}).`,
        rooms: [],
        severity: 'warning',
      });
    }
  }

  rooms.forEach((r) => {
    const hasDoor = allDoors.some((d) => d.between && d.between.includes(r.name));
    if (!hasDoor) {
      problems.push({
        code: 'F1',
        message: `Room '${r.name}' has no door connection! Unreachable from circulation.`,
        rooms: [r.name],
        severity: 'error',
      });
    }
  });

  allDoors.forEach((d) => {
    if (!d.isMainEntrance && d.between && d.between.length === 2) {
      const roomA = roomMap.get(d.between[0]) || hallwaySegments.find((h) => h.id === d.between[0]);
      const roomB = roomMap.get(d.between[1]) || hallwaySegments.find((h) => h.id === d.between[1]);
      if (roomA && roomB) {
        const isVertShared = (roomA.x + roomA.w === roomB.x || roomB.x + roomB.w === roomA.x);
        const isHorizShared = (roomA.y + roomA.h === roomB.y || roomB.y + roomB.h === roomA.y);
        if (!isVertShared && !isHorizShared) {
          problems.push({
            code: 'F2',
            message: `Door between '${d.between[0]}' and '${d.between[1]}' is not placed on a valid shared wall.`,
            rooms: [d.between[0], d.between[1]],
            severity: 'error',
          });
        }
      }
    }
  });

  allDoors.forEach((d) => {
    if (d.width && d.width < 3) {
      problems.push({
        code: 'F3',
        message: `Door width (${d.width} ft) is below standard minimum of 3 ft.`,
        rooms: d.between || [],
        severity: 'error',
      });
    }
  });

  allDoors.forEach((d) => {
    if (d.between) {
      const hasBath = d.between.some((name) => roomMap.get(name)?.type === 'bathroom');
      const hasKitchen = d.between.some((name) => roomMap.get(name)?.type === 'kitchen');
      if (hasBath && hasKitchen) {
        problems.push({
          code: 'F5',
          message: 'Forbidden pattern: Bathroom door directly opens into kitchen.',
          rooms: d.between,
          severity: 'error',
        });
      }
    }
  });

  return problems;
}
