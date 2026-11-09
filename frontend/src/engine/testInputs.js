

export const TEST_INPUTS = [
  {
    id: 'test-1-standard',
    title: 'Test 1: Standard 4-Room (PDF Sample)',
    description: '30x40 ft plot, South entrance, Kitchen SE (try), Bedroom NW (must)',
    input: {
      plot: [30, 40],
      setbacks: { front: 5, back: 3, left: 3, right: 3 },
      entrance: 'S',
      north: 'up',
      rooms: [
        { name: 'living', type: 'living' },
        { name: 'kitchen', type: 'kitchen', zone: 'SE', zone_mode: 'try' },
        { name: 'bedroom', type: 'bedroom', zone: 'NW', zone_mode: 'must' },
        { name: 'bathroom', type: 'bathroom' }
      ],
      pins: []
    }
  },
  {
    id: 'test-2-pinned-edit',
    title: 'Test 2: Pinned Room Edit (Day 8)',
    description: 'Standard 4-room with Bedroom pinned to width = 14 ft',
    input: {
      plot: [30, 40],
      setbacks: { front: 5, back: 3, left: 3, right: 3 },
      entrance: 'S',
      north: 'up',
      rooms: [
        { name: 'living', type: 'living' },
        { name: 'kitchen', type: 'kitchen', zone: 'SE', zone_mode: 'try' },
        { name: 'bedroom', type: 'bedroom', zone: 'NW', zone_mode: 'must' },
        { name: 'bathroom', type: 'bathroom' }
      ],
      pins: [{ room: 'bedroom', width: 14 }]
    }
  },
  {
    id: 'test-3-north-entrance',
    title: 'Test 3: North Entrance Villa',
    description: '32x42 ft plot, North entrance, Living in N (must), Kitchen in E (try)',
    input: {
      plot: [32, 42],
      setbacks: { front: 4, back: 4, left: 3, right: 3 },
      entrance: 'N',
      north: 'up',
      rooms: [
        { name: 'living', type: 'living', zone: 'N', zone_mode: 'must' },
        { name: 'kitchen', type: 'kitchen', zone: 'E', zone_mode: 'try' },
        { name: 'bedroom', type: 'bedroom', zone: 'SW', zone_mode: 'try' },
        { name: 'bathroom', type: 'bathroom' }
      ],
      pins: []
    }
  },
  {
    id: 'test-4-five-rooms',
    title: 'Test 4: 5-Room Family Home (with Dining)',
    description: '36x44 ft plot, South entrance, Living, Dining, Kitchen, Bedroom, Bathroom',
    input: {
      plot: [36, 44],
      setbacks: { front: 5, back: 3, left: 3, right: 3 },
      entrance: 'S',
      north: 'up',
      rooms: [
        { name: 'living', type: 'living', zone: 'S', zone_mode: 'try' },
        { name: 'dining', type: 'dining', zone: 'Mid', zone_mode: 'try' },
        { name: 'kitchen', type: 'kitchen', zone: 'SE', zone_mode: 'must' },
        { name: 'bedroom', type: 'bedroom', zone: 'NW', zone_mode: 'must' },
        { name: 'bathroom', type: 'bathroom' }
      ],
      pins: []
    }
  },
  {
    id: 'test-5-work-from-home',
    title: 'Test 5: Home Study & Living',
    description: '32x38 ft plot, West entrance, Dedicated study (P3 schema)',
    input: {
      plot: [32, 38],
      setbacks: { front: 4, back: 3, left: 3, right: 3 },
      entrance: 'W',
      north: 'up',
      rooms: [
        { name: 'living', type: 'living', zone: 'W', zone_mode: 'must' },
        { name: 'study', type: 'study', zone: 'NW', zone_mode: 'try' },
        { name: 'kitchen', type: 'kitchen', zone: 'SE', zone_mode: 'try' },
        { name: 'bedroom', type: 'bedroom', zone: 'NE', zone_mode: 'try' },
        { name: 'bathroom', type: 'bathroom' }
      ],
      pins: []
    }
  },
  {
    id: 'test-6-attached-bath',
    title: 'Test 6: Attached Bathroom Suite',
    description: 'Master Bedroom with directly connected attached bathroom',
    input: {
      plot: [32, 40],
      setbacks: { front: 4, back: 3, left: 3, right: 3 },
      entrance: 'S',
      north: 'up',
      rooms: [
        { name: 'living', type: 'living', zone: 'S', zone_mode: 'must' },
        { name: 'kitchen', type: 'kitchen', zone: 'SE', zone_mode: 'try' },
        { name: 'master bedroom', type: 'bedroom', zone: 'NW', zone_mode: 'must' },
        { name: 'ensuite bath', type: 'bathroom', attached_to: 'master bedroom' }
      ],
      pins: []
    }
  },
  {
    id: 'test-7-six-rooms-large',
    title: 'Test 7: 6-Room Multi-Bedroom',
    description: '40x48 ft plot, 2 Bedrooms, Dining, Living, Kitchen, Bath',
    input: {
      plot: [40, 48],
      setbacks: { front: 5, back: 4, left: 4, right: 4 },
      entrance: 'S',
      north: 'up',
      rooms: [
        { name: 'living', type: 'living', zone: 'S', zone_mode: 'try' },
        { name: 'kitchen', type: 'kitchen', zone: 'SE', zone_mode: 'try' },
        { name: 'dining', type: 'dining' },
        { name: 'bedroom 1', type: 'bedroom', zone: 'NW', zone_mode: 'must' },
        { name: 'bedroom 2', type: 'bedroom', zone: 'NE', zone_mode: 'try' },
        { name: 'bathroom', type: 'bathroom' }
      ],
      pins: []
    }
  },
  {
    id: 'test-8-narrow-lot',
    title: 'Test 8: Narrow Urban Lot',
    description: '24x45 ft plot, linear flow with central corridor',
    input: {
      plot: [24, 45],
      setbacks: { front: 4, back: 3, left: 2, right: 2 },
      entrance: 'S',
      north: 'up',
      rooms: [
        { name: 'living', type: 'living', zone: 'S', zone_mode: 'must' },
        { name: 'kitchen', type: 'kitchen', zone: 'Mid', zone_mode: 'try' },
        { name: 'bedroom', type: 'bedroom', zone: 'N', zone_mode: 'must' },
        { name: 'bathroom', type: 'bathroom' }
      ],
      pins: []
    }
  },
  {
    id: 'test-9-strict-vastu-zones',
    title: 'Test 9: Strict Must-Have Corners',
    description: 'Kitchen in SE (must), Master Bedroom in SW (must)',
    input: {
      plot: [34, 40],
      setbacks: { front: 5, back: 3, left: 3, right: 3 },
      entrance: 'S',
      north: 'up',
      rooms: [
        { name: 'living', type: 'living', zone: 'S', zone_mode: 'try' },
        { name: 'kitchen', type: 'kitchen', zone: 'SE', zone_mode: 'must' },
        { name: 'bedroom', type: 'bedroom', zone: 'SW', zone_mode: 'must' },
        { name: 'bathroom', type: 'bathroom' }
      ],
      pins: []
    }
  },
  {
    id: 'test-10-border-tight',
    title: 'Test 10: Tight Feasibility Stress Test',
    description: '25x28 ft plot, tight clearance testing minimum room sizes',
    input: {
      plot: [25, 28],
      setbacks: { front: 3, back: 2, left: 2, right: 2 },
      entrance: 'S',
      north: 'up',
      rooms: [
        { name: 'living', type: 'living' },
        { name: 'kitchen', type: 'kitchen' },
        { name: 'bedroom', type: 'bedroom' },
        { name: 'bathroom', type: 'bathroom' }
      ],
      pins: []
    }
  }
];
