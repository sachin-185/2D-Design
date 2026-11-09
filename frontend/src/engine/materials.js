

export const SQFT_TO_SQM = 0.092903;
export const SQM_TO_SQFT = 10.7639;

export const FLOORING_MATERIALS = {
  oak: {
    id: 'oak',
    name: 'Oak Flooring',
    ratePerSqm: 55, 
    color: '#d4a373',
    roughness: 0.4,
    type: 'wood',
    defaultFor: ['living', 'bedroom', 'study', 'dining'],
  },
  antislip: {
    id: 'antislip',
    name: '300 Anti-slip Tile',
    ratePerSqm: 24, 
    color: '#cbd5e1',
    roughness: 0.8,
    type: 'tile',
    defaultFor: ['bathroom', 'utility', 'laundry'],
  },
  porcelain600: {
    id: 'porcelain600',
    name: '600 Porcelain Tile',
    ratePerSqm: 32, 
    color: '#e2e8f0',
    roughness: 0.3,
    type: 'tile',
    defaultFor: ['kitchen', 'store', 'storage'],
  },
  walnut: {
    id: 'walnut',
    name: 'Walnut Flooring',
    ratePerSqm: 68,
    color: '#8b5a2b',
    roughness: 0.4,
    type: 'wood',
    defaultFor: [],
  },
  marble: {
    id: 'marble',
    name: 'Italian Marble',
    ratePerSqm: 110,
    color: '#f8fafc',
    roughness: 0.15,
    type: 'stone',
    defaultFor: [],
  },
};


export function calculateFlooringEstimate(rooms = [], customRoomFlooring = {}) {
  const breakdown = {};
  Object.keys(FLOORING_MATERIALS).forEach((matId) => {
    breakdown[matId] = {
      material: FLOORING_MATERIALS[matId],
      netSqft: 0,
      netSqm: 0,
      withWasteSqm: 0,
      totalCost: 0,
      roomCount: 0,
    };
  });

  let totalNetSqft = 0;
  let totalNetSqm = 0;
  let totalCost = 0;

  const roomAreas = rooms.map((room) => {
    const sqft = (room.w || 0) * (room.h || 0);
    const sqm = sqft * SQFT_TO_SQM;
    totalNetSqft += sqft;
    totalNetSqm += sqm;

    let matId = customRoomFlooring[room.name];
    if (!matId) {
      const found = Object.values(FLOORING_MATERIALS).find((m) =>
        m.defaultFor.includes(room.type)
      );
      matId = found ? found.id : 'oak';
    }

    if (breakdown[matId]) {
      breakdown[matId].netSqft += sqft;
      breakdown[matId].netSqm += sqm;
      breakdown[matId].roomCount += 1;
    }

    return {
      name: room.name,
      type: room.type,
      sqft,
      sqm: Math.round(sqm * 100) / 100,
      materialId: matId,
      material: FLOORING_MATERIALS[matId] || FLOORING_MATERIALS.oak,
    };
  });

  Object.keys(breakdown).forEach((matId) => {
    const item = breakdown[matId];
    item.withWasteSqm = Math.round(item.netSqm * 1.05 * 10) / 10;
    item.totalCost = Math.round(item.withWasteSqm * item.material.ratePerSqm);
    totalCost += item.totalCost;
  });

  return {
    rooms: roomAreas,
    totalNetSqft,
    totalNetSqm: Math.round(totalNetSqm * 100) / 100,
    breakdown: Object.values(breakdown).filter((b) => b.netSqm > 0),
    totalCost,
    wastePercentage: 5,
  };
}

