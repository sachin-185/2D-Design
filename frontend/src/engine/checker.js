import { ROOM_SIZE_TABLE, getBuildableArea } from "./contracts.js";

// Calculate the length of a shared wall between two rectangles.
// Corner contact and non-touching rectangles return 0.
function sharedWallLength(a, b) {
  let best = 0;

  if (a.x + a.w === b.x || b.x + b.w === a.x) {
    best = Math.max(best, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
  }

  if (a.y + a.h === b.y || b.y + b.h === a.y) {
    best = Math.max(best, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
  }

  return Math.max(best, 0);
}

// Build a graph containing rooms and hallway segments.
// Two nodes are connected when they share at least 3 ft of wall.
function buildConnectionGraph(nodes, doorMin = 3) {
  const graph = new Map(nodes.map((node) => [node.name, new Set()]));

  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      if (sharedWallLength(nodes[i], nodes[j]) >= doorMin) {
        graph.get(nodes[i].name).add(nodes[j].name);
        graph.get(nodes[j].name).add(nodes[i].name);
      }
    }
  }

  return graph;
}

// Breadth-first search from a starting node.
function reachableFrom(graph, start) {
  const seen = new Set([start]);
  const queue = [start];

  for (let i = 0; i < queue.length; i++) {
    const current = queue[i];

    for (const next of graph.get(current) || []) {
      if (!seen.has(next)) {
        seen.add(next);
        queue.push(next);
      }
    }
  }

  return seen;
}

export function checkLayout(layout, input, doors = []) {
  const problems = [];
  const buildable = getBuildableArea(input.plot, input.setbacks);
  const W = buildable.width;
  const L = buildable.length;

  const rooms = layout?.rooms || [];
  const hallwaySegments =
    layout?.hallway_segments ||
    (layout?.hallway ? [{ id: "hallway_1", ...layout.hallway }] : []);

  const namedHallways = hallwaySegments.map((hall, index) => ({
    ...hall,
    name: hall.id || `hallway_${index + 1}`,
  }));

  const graphNodes = [...rooms, ...namedHallways];
  const connectionGraph = buildConnectionGraph(graphNodes);

  const allDoors = doors.length > 0 ? doors : layout?.doors || [];

  const roomMap = new Map();
  rooms.forEach((r) => roomMap.set(r.name, r));

  if (!input.rooms || input.rooms.length === 0) {
    problems.push({
      code: "I1",
      message: "No rooms requested in input.",
      rooms: [],
      severity: "error",
    });
  }
  if (input.rooms && input.rooms.length > 10) {
    problems.push({
      code: "I1",
      message: `Room count (${input.rooms.length}) exceeds the maximum limit of 10 rooms.`,
      rooms: input.rooms.map((r) => r.name),
      severity: "error",
    });
  }
  input.rooms?.forEach((r) => {
    if (!ROOM_SIZE_TABLE[r.type]) {
      problems.push({
        code: "I1",
        message: `Invalid room type '${r.type}' for room '${r.name}'. Allowed types: living, kitchen, bedroom, bathroom, dining, study, utility, store, storage, laundry.`,
        rooms: [r.name],
        severity: "error",
      });
    }
  });

  rooms.forEach((r) => {
    if (r.x < 0 || r.y < 0 || r.x + r.w > W || r.y + r.h > L) {
      problems.push({
        code: "H1",
        message: `Room '${r.name}' exceeds buildable area bounds (${W}x${L} ft): placed at (${r.x}, ${r.y}, ${r.w}x${r.h}).`,
        rooms: [r.name],
        severity: "error",
      });
    }
  });

  hallwaySegments.forEach((seg) => {
    if (seg.x < 0 || seg.y < 0 || seg.x + seg.w > W || seg.y + seg.h > L) {
      problems.push({
        code: "H1",
        message: `Hallway segment '${seg.id || "hallway"}' exceeds buildable area bounds (${W}x${L} ft).`,
        rooms: [],
        severity: "error",
      });
    }
  });

  // H2: Room size limits, rotation, input overrides, and pinned dimensions.
  const inputRoomMap = new Map(
    (input.rooms || []).map((room) => [room.name, room]),
  );

  rooms.forEach((room) => {
    const spec = inputRoomMap.get(room.name);

    if (!spec) {
      problems.push({
        code: "H2",
        message: `Room '${room.name}' is not present in the input.`,
        rooms: [room.name],
        severity: "error",
      });
      return;
    }

    const config = ROOM_SIZE_TABLE[spec.type];

    if (!config) {
      problems.push({
        code: "H2",
        message: `No size rule for room type '${spec.type}' (${room.name}).`,
        rooms: [room.name],
        severity: "error",
      });
      return;
    }

    const tableMin = [config.min.w, config.min.h];
    const tableMax = [config.max.w, config.max.h];

    const min = [...(spec.min || tableMin)].sort((a, b) => a - b);
    const max = [...(spec.max || tableMax)].sort((a, b) => a - b);
    const sides = [room.w, room.h].sort((a, b) => a - b);

    if (sides[0] < min[0] || sides[1] < min[1]) {
      problems.push({
        code: "H2",
        message: `Room '${room.name}' (${room.w}x${room.h} ft) is below its minimum of ${min[0]}x${min[1]} ft.`,
        rooms: [room.name],
        severity: "error",
      });
    }

    if (sides[0] > max[0] || sides[1] > max[1]) {
      problems.push({
        code: "H2",
        message: `Room '${room.name}' (${room.w}x${room.h} ft) is above its maximum of ${max[0]}x${max[1]} ft.`,
        rooms: [room.name],
        severity: "error",
      });
    }
  });

  // Check pinned room dimensions.
  (input.pins || []).forEach((pin) => {
    const room = roomMap.get(pin.room);

    if (!room) {
      problems.push({
        code: "H2",
        message: `Pinned room '${pin.room}' is missing.`,
        rooms: [pin.room],
        severity: "error",
      });
      return;
    }

    if (
      Object.prototype.hasOwnProperty.call(pin, "width") &&
      room.w !== pin.width
    ) {
      problems.push({
        code: "H2",
        message: `Room '${pin.room}' width is ${room.w}, pinned to ${pin.width}.`,
        rooms: [pin.room],
        severity: "error",
      });
    }

    if (
      Object.prototype.hasOwnProperty.call(pin, "height") &&
      room.h !== pin.height
    ) {
      problems.push({
        code: "H2",
        message: `Room '${pin.room}' height is ${room.h}, pinned to ${pin.height}.`,
        rooms: [pin.room],
        severity: "error",
      });
    }
  });

  for (let i = 0; i < rooms.length; i++) {
    for (let j = i + 1; j < rooms.length; j++) {
      const a = rooms[i];
      const b = rooms[j];
      const overlapX = Math.max(
        0,
        Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x),
      );
      const overlapY = Math.max(
        0,
        Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y),
      );
      if (overlapX > 0 && overlapY > 0) {
        problems.push({
          code: "H3",
          message: `Rooms '${a.name}' and '${b.name}' overlap by ${overlapX}x${overlapY} ft.`,
          rooms: [a.name, b.name],
          severity: "error",
        });
      }
    }
  }

  // H3: Check room-to-hallway overlap.
  rooms.forEach((r) => {
    hallwaySegments.forEach((seg) => {
      const overlapX = Math.max(
        0,
        Math.min(r.x + r.w, seg.x + seg.w) - Math.max(r.x, seg.x),
      );

      const overlapY = Math.max(
        0,
        Math.min(r.y + r.h, seg.y + seg.h) - Math.max(r.y, seg.y),
      );

      if (overlapX > 0 && overlapY > 0) {
        problems.push({
          code: "H3",
          message: `Room '${r.name}' overlaps with hallway segment '${seg.id || "hallway"}' by ${overlapX}x${overlapY} ft.`,
          rooms: [r.name],
          severity: "error",
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
      code: "H4",
      message: `Partial plot coverage: ${unallocated} sq ft unallocated (${pct}% covered).`,
      rooms: [],
      severity: "warning",
    });
  } else if (totalCovered > buildable.area) {
    problems.push({
      code: "H4",
      message: `Total room area (${totalCovered} sq ft) exceeds buildable area (${buildable.area} sq ft).`,
      rooms: [],
      severity: "error",
    });
  }

  input.rooms?.forEach((req) => {
    if (req.type === "bathroom" && req.attached_to) {
      const bath = roomMap.get(req.name);
      const bed = roomMap.get(req.attached_to);
      if (bath && bed) {
        const sharesWall =
          ((bath.x + bath.w === bed.x || bed.x + bed.w === bath.x) &&
            Math.min(bath.y + bath.h, bed.y + bed.h) -
              Math.max(bath.y, bed.y) >=
              3) ||
          ((bath.y + bath.h === bed.y || bed.y + bed.h === bath.y) &&
            Math.min(bath.x + bath.w, bed.x + bed.w) -
              Math.max(bath.x, bed.x) >=
              3);
        if (!sharesWall) {
          problems.push({
            code: "H6",
            message: `Attached bathroom '${bath.name}' does not share a min 3ft wall with '${bed.name}'.`,
            rooms: [bath.name, bed.name],
            severity: "error",
          });
        }
      }
    }
  });

  const livingRooms = rooms.filter((r) => r.type === "living");
  const kitchen = rooms.find((r) => r.type === "kitchen");

  if (kitchen) {
    const firstLiving = livingRooms[0];

    if (!firstLiving) {
      problems.push({
        code: "H6",
        message: `Kitchen '${kitchen.name}' has no living room to connect to.`,
        rooms: [kitchen.name],
        severity: "error",
      });
    } else {
      const sharesWallLiving =
        ((kitchen.x + kitchen.w === firstLiving.x ||
          firstLiving.x + firstLiving.w === kitchen.x) &&
          Math.min(kitchen.y + kitchen.h, firstLiving.y + firstLiving.h) -
            Math.max(kitchen.y, firstLiving.y) >=
            3) ||
        ((kitchen.y + kitchen.h === firstLiving.y ||
          firstLiving.y + firstLiving.h === kitchen.y) &&
          Math.min(kitchen.x + kitchen.w, firstLiving.x + firstLiving.w) -
            Math.max(kitchen.x, firstLiving.x) >=
            3);

      if (!sharesWallLiving) {
        problems.push({
          code: "H6",
          message: `Kitchen '${kitchen.name}' does not share a wall of at least 3 ft with the first living room '${firstLiving.name}'.`,
          rooms: [kitchen.name, firstLiving.name],
          severity: "error",
        });
      }
    }
  }

  if (hallwaySegments.length > 0) {
    let longestHallwayLength = 0;

    hallwaySegments.forEach((seg) => {
      const shortSide = Math.min(seg.w, seg.h);
      const longSide = Math.max(seg.w, seg.h);

      longestHallwayLength = Math.max(longestHallwayLength, longSide);

      if (shortSide < 3 || shortSide > 4) {
        problems.push({
          code: "HW1",
          message: `Hallway segment '${seg.id || "hallway"}' has a width of ${shortSide} ft. Hallway width must be between 3 and 4 ft.`,
          rooms: [],
          severity: "error",
        });
      }
    });

    if (longestHallwayLength < 12) {
      problems.push({
        code: "HW1",
        message: `Longest hallway segment (${longestHallwayLength} ft) is below the required minimum of 12 ft.`,
        rooms: [],
        severity: "error",
      });
    }
  }

  // HW3: Reject a hallway network containing a complete 5x5 ft square.
  // H3: Check hallway-to-hallway overlap.
  for (let i = 0; i < hallwaySegments.length; i++) {
    for (let j = i + 1; j < hallwaySegments.length; j++) {
      const a = hallwaySegments[i];
      const b = hallwaySegments[j];

      const overlapX = Math.max(
        0,
        Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x),
      );

      const overlapY = Math.max(
        0,
        Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y),
      );

      if (overlapX > 0 && overlapY > 0) {
        problems.push({
          code: "H3",
          message: `Hallway segments '${a.id || "hallway"}' and '${b.id || "hallway"}' overlap by ${overlapX}x${overlapY} ft.`,
          rooms: [a.id || "hallway", b.id || "hallway"],
          severity: "error",
        });
      }
    }
  }

  if (hallwaySegments.length > 0) {
    const minX = Math.min(...hallwaySegments.map((h) => h.x));
    const minY = Math.min(...hallwaySegments.map((h) => h.y));

    const maxX = Math.max(...hallwaySegments.map((h) => h.x + h.w));
    const maxY = Math.max(...hallwaySegments.map((h) => h.y + h.h));

    let hasFiveByFiveSquare = false;

    for (
      let startX = Math.floor(minX);
      startX < Math.floor(maxX) - 4 && !hasFiveByFiveSquare;
      startX++
    ) {
      for (
        let startY = Math.floor(minY);
        startY < Math.floor(maxY) - 4 && !hasFiveByFiveSquare;
        startY++
      ) {
        let squareIsCovered = true;

        for (let dx = 0; dx < 5 && squareIsCovered; dx++) {
          for (let dy = 0; dy < 5; dy++) {
            const cellX = startX + dx + 0.5;
            const cellY = startY + dy + 0.5;

            const covered = hallwaySegments.some(
              (hall) =>
                hall.x <= cellX &&
                cellX < hall.x + hall.w &&
                hall.y <= cellY &&
                cellY < hall.y + hall.h,
            );

            if (!covered) {
              squareIsCovered = false;
              break;
            }
          }
        }

        if (squareIsCovered) {
          problems.push({
            code: "HW3",
            message: `Hallway network contains a complete 5x5 ft square at (${startX}, ${startY}). Hallway area must not accommodate a 5x5 ft square.`,
            rooms: hallwaySegments.map((h) => h.id || "hallway"),
            severity: "error",
          });

          hasFiveByFiveSquare = true;
        }
      }
    }
  }

  // HW2: All hallway segments must form one connected group.
  if (hallwaySegments.length > 1) {
    const graph = hallwaySegments.map(() => new Set());

    for (let i = 0; i < hallwaySegments.length; i++) {
      for (let j = i + 1; j < hallwaySegments.length; j++) {
        const a = hallwaySegments[i];
        const b = hallwaySegments[j];

        const verticalSharedWall =
          a.x + a.w === b.x || b.x + b.w === a.x
            ? Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y))
            : 0;

        const horizontalSharedWall =
          a.y + a.h === b.y || b.y + b.h === a.y
            ? Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x))
            : 0;

        const sharedWallLength = Math.max(
          verticalSharedWall,
          horizontalSharedWall,
        );

        if (sharedWallLength >= 3) {
          graph[i].add(j);
          graph[j].add(i);
        }
      }
    }

    // Traverse the hallway graph from the first segment.
    const visited = new Set([0]);
    const queue = [0];

    for (let index = 0; index < queue.length; index++) {
      const current = queue[index];

      for (const neighbour of graph[current]) {
        if (!visited.has(neighbour)) {
          visited.add(neighbour);
          queue.push(neighbour);
        }
      }
    }

    const disconnected = hallwaySegments
      .map((hall, index) => ({ hall, index }))
      .filter(({ index }) => !visited.has(index))
      .map(({ hall }) => hall.id || "hallway");

    if (disconnected.length > 0) {
      problems.push({
        code: "HW2",
        message: `Hallway segments are disconnected: ${disconnected.join(", ")}.`,
        rooms: disconnected,
        severity: "error",
      });
    }
  }

  // E1: The first requested living room must touch the entrance-side boundary.
  const entrance = input.entrance || "S";
  const north = input.north || "up";

  const entranceEdges = {
    up: {
      N: "top",
      S: "bottom",
      E: "right",
      W: "left",
    },
    down: {
      N: "bottom",
      S: "top",
      E: "left",
      W: "right",
    },
    left: {
      N: "left",
      S: "right",
      E: "top",
      W: "bottom",
    },
    right: {
      N: "right",
      S: "left",
      E: "bottom",
      W: "top",
    },
  };

  const livingRoomName = input.rooms?.find((r) => r.type === "living")?.name;

  const livingRoom = rooms.find((r) => r.name === livingRoomName);

  const entranceEdge = entranceEdges[north]?.[entrance];

  if (livingRoom && entranceEdge) {
    const touchesEntranceEdge = {
      bottom: livingRoom.y === 0,
      top: livingRoom.y + livingRoom.h === L,
      left: livingRoom.x === 0,
      right: livingRoom.x + livingRoom.w === W,
    }[entranceEdge];

    if (!touchesEntranceEdge) {
      problems.push({
        code: "E1",
        message: `Living room '${livingRoom.name}' must touch the ${entranceEdge} edge of the buildable area (entrance side ${entrance}).`,
        rooms: [livingRoom.name],
        severity: "error",
      });
    }
  }

  // Determine the entrance room:
  // first requested living room, or first requested room if no living room exists.
  const entranceRoom =
    input.rooms?.find((room) => room.type === "living") || input.rooms?.[0];

  if (entranceRoom) {
    const entranceName = entranceRoom.name;

    // F5: Every room and hallway must be reachable from the entrance.
    if (!connectionGraph.has(entranceName)) {
      problems.push({
        code: "F5",
        message: `Entrance room '${entranceName}' is not in the layout.`,
        rooms: [entranceName],
        severity: "error",
      });
    } else {
      const reachable = reachableFrom(connectionGraph, entranceName);

      [...connectionGraph.keys()]
        .filter((name) => !reachable.has(name))
        .sort()
        .forEach((name) => {
          problems.push({
            code: "F5",
            message: `'${name}' cannot be reached from '${entranceName}'.`,
            rooms: [name],
            severity: "error",
          });
        });

      // F1: A bedroom must not require walking through another bedroom.
      const reachableWithoutWalkingThroughBedrooms = new Set([entranceName]);
      const queue = [entranceName];

      for (let i = 0; i < queue.length; i++) {
        const current = queue[i];

        // You may enter a bedroom, but cannot continue through it.
        // The entrance room itself is exempt, matching P4.
        if (
          input.rooms?.some(
            (room) => room.name === current && room.type === "bedroom",
          ) &&
          current !== entranceName
        ) {
          continue;
        }

        for (const next of connectionGraph.get(current) || []) {
          if (!reachableWithoutWalkingThroughBedrooms.has(next)) {
            reachableWithoutWalkingThroughBedrooms.add(next);
            queue.push(next);
          }
        }
      }

      const roomTypes = new Map(
        (input.rooms || []).map((room) => [room.name, room.type]),
      );

      [...reachable]
        .filter(
          (name) =>
            roomTypes.get(name) === "bedroom" &&
            !reachableWithoutWalkingThroughBedrooms.has(name),
        )
        .sort()
        .forEach((name) => {
          problems.push({
            code: "F1",
            message: `'${name}' can only be reached through another bedroom.`,
            rooms: [name],
            severity: "error",
          });
        });
    }
  }

  allDoors.forEach((d) => {
    if (!d.isMainEntrance && d.between && d.between.length === 2) {
      const roomA =
        roomMap.get(d.between[0]) ||
        hallwaySegments.find((h) => h.id === d.between[0]);
      const roomB =
        roomMap.get(d.between[1]) ||
        hallwaySegments.find((h) => h.id === d.between[1]);
      if (roomA && roomB) {
        const sharedLength = sharedWallLength(roomA, roomB);
        if (sharedLength < (d.width || 3)) {
          problems.push({
            code: "F2",
            message: `Door between '${d.between[0]}' and '${d.between[1]}' is not placed on a valid shared wall.`,
            rooms: [d.between[0], d.between[1]],
            severity: "error",
          });
        }
      }
    }
  });

  allDoors.forEach((d) => {
    if (d.width && d.width < 3) {
      problems.push({
        code: "F3",
        message: `Door width (${d.width} ft) is below standard minimum of 3 ft.`,
        rooms: d.between || [],
        severity: "error",
      });
    }
  });

  return problems;
}
