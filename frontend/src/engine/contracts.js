

export const ROOM_SIZE_TABLE = {
  living: {
    name: 'Living Room',
    min: { w: 12, h: 12, area: 144 },
    preferred: { w: 15, h: 16, area: 240 },
    max: { w: 20, h: 20, area: 400 },
    color: '#3b82f6', 
    lightColor: 'rgba(59, 130, 246, 0.15)',
    outerWallRequired: true,
  },
  kitchen: {
    name: 'Kitchen',
    min: { w: 8, h: 8, area: 64 },
    preferred: { w: 10, h: 10, area: 100 },
    max: { w: 12, h: 12, area: 144 },
    color: '#10b981', 
    lightColor: 'rgba(16, 185, 129, 0.15)',
    outerWallRequired: true,
  },
  bedroom: {
    name: 'Bedroom',
    min: { w: 10, h: 10, area: 100 },
    preferred: { w: 12, h: 12, area: 144 },
    max: { w: 16, h: 16, area: 256 },
    color: '#8b5cf6', 
    lightColor: 'rgba(139, 92, 246, 0.15)',
    outerWallRequired: true,
  },
  bathroom: {
    name: 'Bathroom',
    min: { w: 5, h: 7, area: 35 },
    preferred: { w: 6, h: 8, area: 48 },
    max: { w: 8, h: 10, area: 80 },
    color: '#06b6d4', 
    lightColor: 'rgba(6, 182, 212, 0.15)',
    outerWallRequired: false,
  },
  dining: {
    name: 'Dining Room',
    min: { w: 10, h: 10, area: 100 },
    preferred: { w: 12, h: 12, area: 144 },
    max: { w: 14, h: 16, area: 224 },
    color: '#f59e0b', 
    lightColor: 'rgba(245, 158, 11, 0.15)',
    outerWallRequired: false,
  },
  study: {
    name: 'Study',
    min: { w: 8, h: 8, area: 64 },
    preferred: { w: 10, h: 10, area: 100 },
    max: { w: 12, h: 14, area: 168 },
    color: '#ec4899', 
    lightColor: 'rgba(236, 72, 153, 0.15)',
    outerWallRequired: true,
  },
  utility: {
    name: 'Utility',
    min: { w: 5, h: 5, area: 25 },
    preferred: { w: 6, h: 6, area: 36 },
    max: { w: 8, h: 8, area: 64 },
    color: '#64748b', 
    lightColor: 'rgba(100, 116, 139, 0.15)',
    outerWallRequired: false,
  },
  store: {
    name: 'Store',
    min: { w: 4, h: 4, area: 16 },
    preferred: { w: 5, h: 5, area: 25 },
    max: { w: 8, h: 8, area: 64 },
    color: '#78716c', 
    lightColor: 'rgba(120, 113, 108, 0.15)',
    outerWallRequired: false,
  },
  storage: {
    name: 'Storage',
    min: { w: 4, h: 4, area: 16 },
    preferred: { w: 5, h: 5, area: 25 },
    max: { w: 8, h: 8, area: 64 },
    color: '#a8a29e', 
    lightColor: 'rgba(168, 162, 158, 0.15)',
    outerWallRequired: false,
  },
  laundry: {
    name: 'Laundry',
    min: { w: 5, h: 5, area: 25 },
    preferred: { w: 6, h: 6, area: 36 },
    max: { w: 8, h: 8, area: 64 },
    color: '#0284c7', 
    lightColor: 'rgba(2, 132, 199, 0.15)',
    outerWallRequired: false,
  },
};

export const ZONES = ['NW', 'N', 'NE', 'W', 'Mid', 'E', 'SW', 'S', 'SE'];

export const ZONE_GRID_MAP = {
  NW: { col: 0, row: 2 },
  N:  { col: 1, row: 2 },
  NE: { col: 2, row: 2 },
  W:  { col: 0, row: 1 },
  Mid:{ col: 1, row: 1 },
  E:  { col: 2, row: 1 },
  SW: { col: 0, row: 0 },
  S:  { col: 1, row: 0 },
  SE: { col: 2, row: 0 },
};


export function getBuildableArea(plot, setbacks) {
  const [plotW, plotL] = plot;
  const left = setbacks?.left || 0;
  const right = setbacks?.right || 0;
  const front = setbacks?.front || 0;
  const back = setbacks?.back || 0;

  const buildableW = Math.max(0, plotW - left - right);
  const buildableL = Math.max(0, plotL - front - back);
  const area = buildableW * buildableL;

  return {
    originX: left,
    originY: back, 
    width: buildableW,
    length: buildableL,
    area,
  };
}


export function checkFeasibility(plot, setbacks, rooms) {
  const buildable = getBuildableArea(plot, setbacks);
  let minRoomsArea = 0;

  for (const room of rooms) {
    const config = ROOM_SIZE_TABLE[room.type] || {
      min: { w: 8, h: 8, area: 64 },
    };
    minRoomsArea += config.min.area || config.min.w * config.min.h;
  }

  const circulation = Math.round(minRoomsArea * 0.15);
  const totalRequired = minRoomsArea + circulation;
  const feasible = totalRequired <= buildable.area && buildable.width > 0 && buildable.length > 0;
  const shortfall = feasible ? 0 : Math.max(0, totalRequired - buildable.area);

  return {
    feasible,
    buildableArea: buildable.area,
    buildableW: buildable.width,
    buildableL: buildable.length,
    minRoomsArea,
    circulation,
    totalRequired,
    shortfall,
    message: feasible
      ? `Buildable area of ${buildable.area} sq ft accommodates required minimum ${totalRequired} sq ft (${minRoomsArea} sq ft rooms + ${circulation} sq ft circulation).`
      : `Plot is too small by ${shortfall} sq ft. Total required: ${totalRequired} sq ft (rooms: ${minRoomsArea} sq ft, circulation: ${circulation} sq ft) vs buildable: ${buildable.area} sq ft.`,
  };
}
