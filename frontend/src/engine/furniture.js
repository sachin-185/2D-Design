

export const FURNITURE_CATALOG = [
  {
    id: 'double-bed',
    category: 'bedroom',
    name: 'Double Bed 1.8m',
    dimsLabel: '1800×2000 mm',
    w: 6.0,
    h: 6.5,
    zHeight: 2.2,
    color: '#e2d4c0',
    accentColor: '#938173',
  },
  {
    id: 'single-bed',
    category: 'bedroom',
    name: 'Single Bed 1.2m',
    dimsLabel: '1200×2000 mm',
    w: 4.0,
    h: 6.5,
    zHeight: 2.0,
    color: '#e2d4c0',
    accentColor: '#938173',
  },
  {
    id: 'nightstand',
    category: 'bedroom',
    name: 'Nightstand',
    dimsLabel: '450×400 mm',
    w: 1.5,
    h: 1.5,
    zHeight: 1.8,
    color: '#a07855',
    accentColor: '#d4a373',
  },
  {
    id: 'wardrobe',
    category: 'bedroom',
    name: 'Wardrobe 2.0m',
    dimsLabel: '2000×600 mm',
    w: 6.5,
    h: 2.0,
    zHeight: 6.8,
    color: '#8b5a2b',
    accentColor: '#6f4518',
  },
  {
    id: 'dresser',
    category: 'bedroom',
    name: 'Dresser',
    dimsLabel: '1000×450 mm',
    w: 3.5,
    h: 1.5,
    zHeight: 2.8,
    color: '#c49a6c',
    accentColor: '#a07855',
  },

  {
    id: 'sofa-3seat',
    category: 'living',
    name: '3-Seat Sofa',
    dimsLabel: '2100×900 mm',
    w: 7.0,
    h: 3.0,
    zHeight: 2.6,
    color: '#5b7065',
    accentColor: '#40534c',
  },
  {
    id: 'coffee-table',
    category: 'living',
    name: 'Coffee Table',
    dimsLabel: '1200×600 mm',
    w: 4.0,
    h: 2.0,
    zHeight: 1.4,
    color: '#d4a373',
    accentColor: '#b08968',
  },
  {
    id: 'tv-console',
    category: 'living',
    name: 'TV Console',
    dimsLabel: '1800×450 mm',
    w: 6.0,
    h: 1.5,
    zHeight: 1.8,
    color: '#3d342d',
    accentColor: '#1f1b18',
  },
  {
    id: 'armchair',
    category: 'living',
    name: 'Lounge Armchair',
    dimsLabel: '850×850 mm',
    w: 2.8,
    h: 2.8,
    zHeight: 2.6,
    color: '#d4a373',
    accentColor: '#b08968',
  },
  {
    id: 'plant',
    category: 'living',
    name: 'Fiddle Leaf Plant',
    dimsLabel: '500×500 mm',
    w: 1.5,
    h: 1.5,
    zHeight: 4.0,
    color: '#2d6a4f',
    accentColor: '#1b4332',
  },

  {
    id: 'dining-table-4',
    category: 'dining',
    name: 'Dining Table (4-Seat)',
    dimsLabel: '1400×800 mm',
    w: 5.0,
    h: 3.0,
    zHeight: 2.5,
    color: '#8b5a2b',
    accentColor: '#e6ccb2',
  },

  {
    id: 'kitchen-counter',
    category: 'kitchen',
    name: 'Kitchen Counter & Stove',
    dimsLabel: '2400×600 mm',
    w: 8.0,
    h: 2.0,
    zHeight: 3.0,
    color: '#e2e8f0',
    accentColor: '#334155',
  },
  {
    id: 'refrigerator',
    category: 'kitchen',
    name: 'Double Refrigerator',
    dimsLabel: '900×700 mm',
    w: 3.0,
    h: 2.5,
    zHeight: 6.0,
    color: '#94a3b8',
    accentColor: '#64748b',
  },

  {
    id: 'toilet',
    category: 'bathroom',
    name: 'Toilet Suite',
    dimsLabel: '400×650 mm',
    w: 1.5,
    h: 2.2,
    zHeight: 2.5,
    color: '#ffffff',
    accentColor: '#cbd5e1',
  },
  {
    id: 'vanity-sink',
    category: 'bathroom',
    name: 'Vanity & Basin',
    dimsLabel: '900×500 mm',
    w: 3.0,
    h: 1.8,
    zHeight: 2.8,
    color: '#ffffff',
    accentColor: '#64748b',
  },
  {
    id: 'shower',
    category: 'bathroom',
    name: 'Walk-in Glass Shower',
    dimsLabel: '1000×1000 mm',
    w: 3.5,
    h: 3.5,
    zHeight: 6.5,
    color: '#bae6fd',
    accentColor: '#0284c7',
  },

  {
    id: 'desk',
    category: 'study',
    name: 'Executive Workstation',
    dimsLabel: '1500×750 mm',
    w: 5.0,
    h: 2.5,
    zHeight: 2.5,
    color: '#8b5a2b',
    accentColor: '#2b2d42',
  },
];


export function generateAutoFurniture(rooms = []) {
  const items = [];
  let idCounter = 1;

  rooms.forEach((room) => {
    const rx = room.x;
    const ry = room.y;
    const rw = room.w;
    const rh = room.h;
    const type = room.type;

    if (type === 'bedroom') {
      const bedW = 6.0;
      const bedH = 6.5;
      const bedX = rx + (rw - bedW) / 2;
      const bedY = ry + rh - bedH - 0.5;

      items.push({
        id: `furn-${idCounter++}`,
        catalogId: 'double-bed',
        roomName: room.name,
        name: 'Double Bed',
        x: Math.max(rx + 0.5, bedX),
        y: Math.max(ry + 0.5, bedY),
        w: bedW,
        h: bedH,
        zHeight: 2.2,
        color: '#f0ede6',
        accentColor: '#7a6f64',
        type: 'bed',
      });

      if (bedX - rx >= 2.0) {
        items.push({
          id: `furn-${idCounter++}`,
          catalogId: 'nightstand',
          roomName: room.name,
          name: 'Nightstand L',
          x: rx + 0.5,
          y: ry + rh - 2.0,
          w: 1.5,
          h: 1.5,
          zHeight: 1.8,
          color: '#a07855',
          accentColor: '#d4a373',
          type: 'table',
        });
      }

      if (rx + rw - (bedX + bedW) >= 2.0) {
        items.push({
          id: `furn-${idCounter++}`,
          catalogId: 'nightstand',
          roomName: room.name,
          name: 'Nightstand R',
          x: rx + rw - 2.0,
          y: ry + rh - 2.0,
          w: 1.5,
          h: 1.5,
          zHeight: 1.8,
          color: '#a07855',
          accentColor: '#d4a373',
          type: 'table',
        });
      }

      if (rw >= 11 && rh >= 10) {
        items.push({
          id: `furn-${idCounter++}`,
          catalogId: 'wardrobe',
          roomName: room.name,
          name: 'Wardrobe',
          x: rx + 0.8,
          y: ry + 0.8,
          w: 6.0,
          h: 2.0,
          zHeight: 6.8,
          color: '#8b5a2b',
          accentColor: '#5c3a1e',
          type: 'storage',
        });
      }
    } else if (type === 'living') {
      const sofaW = Math.min(rw - 3, 7.5);
      const sofaH = 3.0;
      items.push({
        id: `furn-${idCounter++}`,
        catalogId: 'sofa-3seat',
        roomName: room.name,
        name: '3-Seat Sofa',
        x: rx + 1.2,
        y: ry + rh - sofaH - 1.2,
        w: sofaW,
        h: sofaH,
        zHeight: 2.6,
        color: '#65776d',
        accentColor: '#45524a',
        type: 'sofa',
      });

      items.push({
        id: `furn-${idCounter++}`,
        catalogId: 'coffee-table',
        roomName: room.name,
        name: 'Coffee Table',
        x: rx + 2.5,
        y: ry + rh - sofaH - 3.8,
        w: 4.5,
        h: 2.0,
        zHeight: 1.4,
        color: '#d4a373',
        accentColor: '#a07855',
        type: 'table',
      });

      if (rh >= 12) {
        items.push({
          id: `furn-${idCounter++}`,
          catalogId: 'tv-console',
          roomName: room.name,
          name: 'Media Console & TV',
          x: rx + 2.0,
          y: ry + 0.8,
          w: 6.0,
          h: 1.5,
          zHeight: 2.0,
          color: '#2b2a29',
          accentColor: '#121110',
          type: 'storage',
        });
      }

      if (rw >= 13) {
        items.push({
          id: `furn-${idCounter++}`,
          catalogId: 'armchair',
          roomName: room.name,
          name: 'Lounge Chair',
          x: rx + rw - 3.8,
          y: ry + rh - 4.5,
          w: 2.8,
          h: 2.8,
          zHeight: 2.6,
          color: '#d4a373',
          accentColor: '#b08968',
          type: 'sofa',
        });
      }

      items.push({
        id: `furn-${idCounter++}`,
        catalogId: 'plant',
        roomName: room.name,
        name: 'Fiddle Leaf Fig',
        x: rx + rw - 2.2,
        y: ry + rh - 2.2,
        w: 1.5,
        h: 1.5,
        zHeight: 4.5,
        color: '#2d6a4f',
        accentColor: '#1b4332',
        type: 'decor',
      });
    } else if (type === 'kitchen') {
      const counterW = Math.max(5, rw - 1.5);
      items.push({
        id: `furn-${idCounter++}`,
        catalogId: 'kitchen-counter',
        roomName: room.name,
        name: 'Main Counter & Cooktop',
        x: rx + 0.8,
        y: ry + rh - 2.5,
        w: counterW,
        h: 2.0,
        zHeight: 3.0,
        color: '#f8fafc',
        accentColor: '#334155',
        type: 'counter',
      });

      items.push({
        id: `furn-${idCounter++}`,
        catalogId: 'refrigerator',
        roomName: room.name,
        name: 'French Door Fridge',
        x: rx + 0.8,
        y: ry + 0.8,
        w: 3.0,
        h: 2.5,
        zHeight: 6.2,
        color: '#94a3b8',
        accentColor: '#475569',
        type: 'appliance',
      });
    } else if (type === 'bathroom') {
      items.push({
        id: `furn-${idCounter++}`,
        catalogId: 'vanity-sink',
        roomName: room.name,
        name: 'Vanity & Basin',
        x: rx + 0.6,
        y: ry + rh - 2.2,
        w: 3.0,
        h: 1.6,
        zHeight: 2.8,
        color: '#ffffff',
        accentColor: '#64748b',
        type: 'bath',
      });

      items.push({
        id: `furn-${idCounter++}`,
        catalogId: 'toilet',
        roomName: room.name,
        name: 'Toilet Suite',
        x: rx + rw - 2.2,
        y: ry + rh - 2.5,
        w: 1.6,
        h: 2.0,
        zHeight: 2.4,
        color: '#ffffff',
        accentColor: '#cbd5e1',
        type: 'bath',
      });

      if (rw >= 5 && rh >= 7) {
        items.push({
          id: `furn-${idCounter++}`,
          catalogId: 'shower',
          roomName: room.name,
          name: 'Walk-in Shower',
          x: rx + 0.6,
          y: ry + 0.6,
          w: 3.5,
          h: 3.2,
          zHeight: 6.8,
          color: '#e0f2fe',
          accentColor: '#0284c7',
          type: 'bath',
        });
      }
    } else if (type === 'dining') {
      const tableW = 5.0;
      const tableH = 3.0;
      items.push({
        id: `furn-${idCounter++}`,
        catalogId: 'dining-table-4',
        roomName: room.name,
        name: 'Dining Set (6-Seat)',
        x: rx + (rw - tableW) / 2,
        y: ry + (rh - tableH) / 2,
        w: tableW,
        h: tableH,
        zHeight: 2.5,
        color: '#8b5a2b',
        accentColor: '#e6ccb2',
        type: 'table',
      });
    } else if (type === 'study') {
      items.push({
        id: `furn-${idCounter++}`,
        catalogId: 'desk',
        roomName: room.name,
        name: 'Work Desk & Chair',
        x: rx + 1.0,
        y: ry + rh - 3.2,
        w: 5.0,
        h: 2.5,
        zHeight: 2.5,
        color: '#8b5a2b',
        accentColor: '#334155',
        type: 'table',
      });
    }
  });

  return items;
}

