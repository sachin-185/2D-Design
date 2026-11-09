

export function findSharedWalls(nodeA, nodeB) {
  const aLeft = nodeA.x;
  const aRight = nodeA.x + nodeA.w;
  const aBottom = nodeA.y;
  const aTop = nodeA.y + nodeA.h;

  const bLeft = nodeB.x;
  const bRight = nodeB.x + nodeB.w;
  const bBottom = nodeB.y;
  const bTop = nodeB.y + nodeB.h;

  if (aRight === bLeft || aLeft === bRight) {
    const sharedX = aRight === bLeft ? aRight : aLeft;
    const overlapStart = Math.max(aBottom, bBottom);
    const overlapEnd = Math.min(aTop, bTop);
    const overlapLen = overlapEnd - overlapStart;

    if (overlapLen >= 3) {
      return {
        type: 'vertical',
        x: sharedX,
        yStart: overlapStart,
        yEnd: overlapEnd,
        length: overlapLen,
        roomLeft: aRight === bLeft ? (nodeA.id || nodeA.name) : (nodeB.id || nodeB.name),
        roomRight: aRight === bLeft ? (nodeB.id || nodeB.name) : (nodeA.id || nodeA.name),
      };
    }
  }

  if (aTop === bBottom || aBottom === bTop) {
    const sharedY = aTop === bBottom ? aTop : aBottom;
    const overlapStart = Math.max(aLeft, bLeft);
    const overlapEnd = Math.min(aRight, bRight);
    const overlapLen = overlapEnd - overlapStart;

    if (overlapLen >= 3) {
      return {
        type: 'horizontal',
        y: sharedY,
        xStart: overlapStart,
        xEnd: overlapEnd,
        length: overlapLen,
        roomBottom: aTop === bBottom ? (nodeA.id || nodeA.name) : (nodeB.id || nodeB.name),
        roomTop: aTop === bBottom ? (nodeB.id || nodeB.name) : (nodeA.id || nodeA.name),
      };
    }
  }

  return null;
}


export function placeDoors(rooms, hallwaySegments = [], entranceSide = 'S', buildableBounds, inputRoomRequests = []) {
  const doors = [];
  const unconnectedRooms = [];
  const doorWidth = 3.0; 

  const segments = Array.isArray(hallwaySegments) ? hallwaySegments : (hallwaySegments ? [{ id: 'hallway_1', ...hallwaySegments }] : []);
  const livingRooms = rooms.filter((r) => r.type === 'living' || r.name.toLowerCase().includes('living'));
  const firstLiving = livingRooms[0] || null;

  const reqMap = new Map();
  inputRoomRequests.forEach((req) => reqMap.set(req.name, req));

  rooms.forEach((room) => {
    if (room === firstLiving && segments.length === 0) {
      return;
    }

    const req = reqMap.get(room.name);
    let placed = false;

    if (room.type === 'bathroom' && req?.attached_to) {
      const targetBed = rooms.find((r) => r.name === req.attached_to);
      if (targetBed) {
        const shared = findSharedWalls(room, targetBed);
        if (shared) {
          if (shared.type === 'vertical') {
            const doorY = shared.length >= 5 ? shared.yStart + 1 : shared.yStart;
            doors.push({
              id: `door-${room.name}-${targetBed.name}`,
              between: [room.name, targetBed.name],
              orientation: 'vertical',
              x: shared.x,
              y: Math.round(doorY * 10) / 10,
              width: doorWidth,
              swingDir: 'in',
            });
            placed = true;
          } else {
            const doorX = shared.length >= 5 ? shared.xStart + 1 : shared.xStart;
            doors.push({
              id: `door-${room.name}-${targetBed.name}`,
              between: [room.name, targetBed.name],
              orientation: 'horizontal',
              x: Math.round(doorX * 10) / 10,
              y: shared.y,
              width: doorWidth,
              swingDir: 'in',
            });
            placed = true;
          }
        }
      }
      if (!placed) {
        unconnectedRooms.push({
          room: room.name,
          reason: `Attached bathroom '${room.name}' cannot connect to bedroom '${req.attached_to}' (no shared wall >= 3 ft).`,
        });
      }
      return;
    }

    if (room.type === 'kitchen' && firstLiving) {
      const sharedLiving = findSharedWalls(room, firstLiving);
      if (sharedLiving) {
        if (sharedLiving.type === 'vertical') {
          const doorY = sharedLiving.length >= 5 ? sharedLiving.yStart + 1 : sharedLiving.yStart;
          doors.push({
            id: `door-${room.name}-${firstLiving.name}`,
            between: [room.name, firstLiving.name],
            orientation: 'vertical',
            x: sharedLiving.x,
            y: Math.round(doorY * 10) / 10,
            width: doorWidth,
            swingDir: 'in',
          });
          placed = true;
        } else {
          const doorX = sharedLiving.length >= 5 ? sharedLiving.xStart + 1 : sharedLiving.xStart;
          doors.push({
            id: `door-${room.name}-${firstLiving.name}`,
            between: [room.name, firstLiving.name],
            orientation: 'horizontal',
            x: Math.round(doorX * 10) / 10,
            y: sharedLiving.y,
            width: doorWidth,
            swingDir: 'in',
          });
          placed = true;
        }
      }
    }

    if (!placed && segments.length > 0) {
      for (const seg of segments) {
        const shared = findSharedWalls(room, seg);
        if (shared) {
          if (shared.type === 'vertical') {
            const doorY = shared.length >= 5 ? shared.yStart + 1 : shared.yStart;
            doors.push({
              id: `door-${room.name}-${seg.id || 'hallway'}`,
              between: [room.name, seg.id || 'hallway'],
              orientation: 'vertical',
              x: shared.x,
              y: Math.round(doorY * 10) / 10,
              width: doorWidth,
              swingDir: 'in',
            });
            placed = true;
            break;
          } else {
            const doorX = shared.length >= 5 ? shared.xStart + 1 : shared.xStart;
            doors.push({
              id: `door-${room.name}-${seg.id || 'hallway'}`,
              between: [room.name, seg.id || 'hallway'],
              orientation: 'horizontal',
              x: Math.round(doorX * 10) / 10,
              y: shared.y,
              width: doorWidth,
              swingDir: 'in',
            });
            placed = true;
            break;
          }
        }
      }
    }

    if (!placed) {
      for (const liv of livingRooms) {
        if (liv.name !== room.name) {
          const shared = findSharedWalls(room, liv);
          if (shared) {
            if (shared.type === 'vertical') {
              const doorY = shared.length >= 5 ? shared.yStart + 1 : shared.yStart;
              doors.push({
                id: `door-${room.name}-${liv.name}`,
                between: [room.name, liv.name],
                orientation: 'vertical',
                x: shared.x,
                y: Math.round(doorY * 10) / 10,
                width: doorWidth,
                swingDir: 'in',
              });
              placed = true;
              break;
            } else {
              const doorX = shared.length >= 5 ? shared.xStart + 1 : shared.xStart;
              doors.push({
                id: `door-${room.name}-${liv.name}`,
                between: [room.name, liv.name],
                orientation: 'horizontal',
                x: Math.round(doorX * 10) / 10,
                y: shared.y,
                width: doorWidth,
                swingDir: 'in',
              });
              placed = true;
              break;
            }
          }
        }
      }
    }

    if (!placed) {
      unconnectedRooms.push({
        room: room.name,
        reason: `Room '${room.name}' has no shared wall >= 3 ft with hallway or living room.`,
      });
    }
  });

  if (segments.length > 1) {
    for (let i = 0; i < segments.length - 1; i++) {
      const segA = segments[i];
      const segB = segments[i + 1];
      const shared = findSharedWalls(segA, segB);
      if (shared) {
        doors.push({
          id: `door-${segA.id}-${segB.id}`,
          between: [segA.id, segB.id],
          orientation: shared.type,
          x: shared.type === 'vertical' ? shared.x : shared.xStart,
          y: shared.type === 'vertical' ? shared.yStart : shared.y,
          width: doorWidth,
          swingDir: 'open',
        });
      }
    }
  }

  if (buildableBounds) {
    const W = buildableBounds.width;
    const L = buildableBounds.length;
    let mainDoor = null;

    if (entranceSide === 'S') {
      const candidate = segments.find((s) => Math.abs(s.y) < 0.1) ||
                        rooms.find((r) => Math.abs(r.y) < 0.1 && (r.type === 'living' || r === firstLiving));
      if (candidate) {
        const doorX = candidate.x + (candidate.w - 3.5) / 2;
        mainDoor = {
          id: 'door-main-entrance',
          isMainEntrance: true,
          between: ['exterior', candidate.id || candidate.name],
          orientation: 'horizontal',
          x: Math.round(doorX * 10) / 10,
          y: 0,
          width: 3.5,
          swingDir: 'in',
        };
      }
    } else if (entranceSide === 'N') {
      const candidate = segments.find((s) => Math.abs(s.y + s.h - L) < 0.1) ||
                        rooms.find((r) => Math.abs(r.y + r.h - L) < 0.1 && (r.type === 'living' || r === firstLiving));
      if (candidate) {
        const doorX = candidate.x + (candidate.w - 3.5) / 2;
        mainDoor = {
          id: 'door-main-entrance',
          isMainEntrance: true,
          between: ['exterior', candidate.id || candidate.name],
          orientation: 'horizontal',
          x: Math.round(doorX * 10) / 10,
          y: L,
          width: 3.5,
          swingDir: 'in',
        };
      }
    } else if (entranceSide === 'E') {
      const candidate = rooms.find((r) => Math.abs(r.x + r.w - W) < 0.1 && (r.type === 'living' || r === firstLiving));
      if (candidate) {
        const doorY = candidate.y + (candidate.h - 3.5) / 2;
        mainDoor = {
          id: 'door-main-entrance',
          isMainEntrance: true,
          between: ['exterior', candidate.id || candidate.name],
          orientation: 'vertical',
          x: W,
          y: Math.round(doorY * 10) / 10,
          width: 3.5,
          swingDir: 'in',
        };
      }
    } else if (entranceSide === 'W') {
      const candidate = rooms.find((r) => Math.abs(r.x) < 0.1 && (r.type === 'living' || r === firstLiving));
      if (candidate) {
        const doorY = candidate.y + (candidate.h - 3.5) / 2;
        mainDoor = {
          id: 'door-main-entrance',
          isMainEntrance: true,
          between: ['exterior', candidate.id || candidate.name],
          orientation: 'vertical',
          x: 0,
          y: Math.round(doorY * 10) / 10,
          width: 3.5,
          swingDir: 'in',
        };
      }
    }

    if (mainDoor) {
      doors.unshift(mainDoor);
    }
  }

  return { doors, unconnectedRooms };
}


export function placeWindows(rooms, buildableBounds) {
  const windows = [];
  const W = buildableBounds.width;
  const L = buildableBounds.length;
  const windowWidth = 3.5;

  rooms.forEach((room) => {
    const touchesSouth = Math.abs(room.y) < 0.1;
    const touchesNorth = Math.abs(room.y + room.h - L) < 0.1;
    const touchesWest = Math.abs(room.x) < 0.1;
    const touchesEast = Math.abs(room.x + room.w - W) < 0.1;

    let windowCount = 0;

    if (touchesSouth && windowCount < 2) {
      windows.push({
        id: `win-${room.name}-S`,
        room: room.name,
        wall: 'S',
        orientation: 'horizontal',
        x: Math.round((room.x + (room.w - windowWidth) / 2) * 10) / 10,
        y: 0,
        width: windowWidth,
      });
      windowCount++;
    }

    if (touchesNorth && windowCount < 2) {
      windows.push({
        id: `win-${room.name}-N`,
        room: room.name,
        wall: 'N',
        orientation: 'horizontal',
        x: Math.round((room.x + (room.w - windowWidth) / 2) * 10) / 10,
        y: L,
        width: windowWidth,
      });
      windowCount++;
    }

    if (touchesWest && windowCount < 2) {
      windows.push({
        id: `win-${room.name}-W`,
        room: room.name,
        wall: 'W',
        orientation: 'vertical',
        x: 0,
        y: Math.round((room.y + (room.h - windowWidth) / 2) * 10) / 10,
        width: windowWidth,
      });
      windowCount++;
    }

    if (touchesEast && windowCount < 2) {
      windows.push({
        id: `win-${room.name}-E`,
        room: room.name,
        wall: 'E',
        orientation: 'vertical',
        x: W,
        y: Math.round((room.y + (room.h - windowWidth) / 2) * 10) / 10,
        width: windowWidth,
      });
      windowCount++;
    }
  });

  return windows;
}
