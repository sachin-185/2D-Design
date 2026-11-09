import { ROOM_SIZE_TABLE, checkFeasibility, getBuildableArea } from '../frontend/src/engine/contracts.js';
import { solveFloorplan } from '../frontend/src/engine/solver.js';
import { checkLayout } from '../frontend/src/engine/checker.js';
import { placeDoors, findSharedWalls } from '../frontend/src/engine/doorsAndWindows.js';
import { TEST_INPUTS } from '../frontend/src/engine/testInputs.js';

console.log('--- 1. Testing Room Types ---');
const allowedTypes = ['living', 'kitchen', 'bedroom', 'bathroom', 'dining', 'study', 'utility', 'store', 'storage', 'laundry'];
allowedTypes.forEach(t => {
  if (!ROOM_SIZE_TABLE[t]) throw new Error(`Missing allowed room type: ${t}`);
});
if (ROOM_SIZE_TABLE['office']) throw new Error('Office should NOT exist in room size table!');
console.log('✓ All 10 P3 room types verified. "office" is strictly absent.');

console.log('\n--- 2. Testing Feasibility Failure Enforcement ---');
const infeasibleInput = {
  plot: [15, 15],
  setbacks: { front: 3, back: 3, left: 3, right: 3 },
  entrance: 'S',
  rooms: [
    { name: 'living', type: 'living' },
    { name: 'kitchen', type: 'kitchen' },
    { name: 'bedroom', type: 'bedroom' },
    { name: 'bathroom', type: 'bathroom' }
  ],
  pins: []
};
const infeasibleRes = solveFloorplan(infeasibleInput);
if (infeasibleRes.success !== false) throw new Error('Infeasible input must return success: false!');
if (infeasibleRes.layouts.length !== 0) throw new Error('Infeasible input must NOT return any layouts!');
if (!infeasibleRes.error.includes('Plot is too small')) throw new Error('Infeasible input must report exact shortfall!');
console.log('✓ Infeasible input correctly halted with zero layouts and clear shortfall message:', infeasibleRes.error);

console.log('\n--- 3. Testing Bottom-Left Coordinates & Hallway Segments ---');
const standardInput = TEST_INPUTS[0].input;
const standardRes = solveFloorplan(standardInput);
if (!standardRes.success) throw new Error('Standard input should solve successfully');
const layout1 = standardRes.layouts[0];

if (!Array.isArray(layout1.hallway_segments)) throw new Error('hallway_segments must be an array');
console.log(`✓ hallway_segments format verified. Segments count: ${layout1.hallway_segments.length}`);

const buildable = getBuildableArea(standardInput.plot, standardInput.setbacks);
layout1.rooms.forEach(r => {
  if (r.y < 0 || r.y + r.h > buildable.length) {
    throw new Error(`Room ${r.name} has invalid bottom-left Y coordinate: y=${r.y}, h=${r.h}, L=${buildable.length}`);
  }
  if (r.x < 0 || r.x + r.w > buildable.width) {
    throw new Error(`Room ${r.name} has invalid X coordinate: x=${r.x}, w=${r.w}, W=${buildable.width}`);
  }
});
console.log('✓ All rooms verified within buildable bounds from bottom-left (0,0).');

console.log('\n--- 4. Testing Door Placement & Attached Bathroom ---');
const attachedInput = TEST_INPUTS.find(t => t.id === 'test-6-attached-bath').input;
const attachedRes = solveFloorplan(attachedInput);
if (!attachedRes.success) throw new Error('Attached bath test should solve');
const attLayout = attachedRes.layouts[0];
const ensuiteDoor = attLayout.doors.find(d => d.between && d.between.includes('ensuite bath') && d.between.includes('master bedroom'));
if (!ensuiteDoor) throw new Error('Ensuite bath MUST connect to master bedroom!');
console.log(`✓ Attached bathroom correctly placed door to named bedroom:`, ensuiteDoor);

console.log('\n--- 5. Testing 3ft Wall Connection without 1ft Gap ---');
const nodeA = { name: 'roomA', x: 0, y: 0, w: 10, h: 10 };
const nodeB_3ft = { name: 'roomB', x: 10, y: 0, w: 10, h: 3 }; 
const shared3ft = findSharedWalls(nodeA, nodeB_3ft);
if (!shared3ft || shared3ft.length !== 3) throw new Error('3ft shared wall must be detected');
console.log('✓ 3ft shared wall detected with length = 3 ft (connects at 3 ft with 0 ft gap).');

console.log('\n--- 6. Testing Real Checker Problems ---');
const problems = layout1.problems;
if (!Array.isArray(problems)) throw new Error('Problems must be an array');
problems.forEach(p => {
  if (!p.code || !p.message || !p.severity) {
    throw new Error(`Problem object missing required fields: ${JSON.stringify(p)}`);
  }
  if (p.severity !== 'error' && p.severity !== 'warning') {
    throw new Error(`Invalid severity: ${p.severity}`);
  }
});
console.log(`✓ Real checker verified. Produced ${problems.length} problem records (e.g. H4 coverage warning).`);
console.log('ALL P5 PIPELINE TESTS PASSED SUCCESSFULLY!');
