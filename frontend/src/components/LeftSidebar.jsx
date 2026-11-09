import React, { useState } from 'react';
import { 
  Plus, 
  Trash2, 
  Sliders, 
  Layers, 
  Box, 
  Sparkles, 
  CheckCircle2, 
  AlertCircle,
  Bed, 
  Armchair, 
  Utensils, 
  Bath, 
  Briefcase
} from 'lucide-react';
import { ROOM_SIZE_TABLE, ZONES, checkFeasibility, getBuildableArea } from '../engine/contracts';
import { FURNITURE_CATALOG } from '../engine/furniture';
import { TEST_INPUTS } from '../engine/testInputs';

export default function LeftSidebar({
  activeTab = 'site',
  onSelectTab,
  layout,
  input,
  onChangeInput,
  onSolve,
  isSolving,
  onAddFurnitureItem,
  onAutoFurnish,
}) {
  const [selectedPresetId, setSelectedPresetId] = useState('test-1-standard');
  const [furnitureCategory, setFurnitureCategory] = useState('all');

  const buildable = getBuildableArea(input.plot, input.setbacks);
  const feasibility = checkFeasibility(input.plot, input.setbacks, input.rooms);

  const filteredFurniture = furnitureCategory === 'all'
    ? FURNITURE_CATALOG
    : FURNITURE_CATALOG.filter((f) => f.category === furnitureCategory);

  const handlePlotChange = (idx, value) => {
    const val = Math.max(10, parseInt(value, 10) || 10);
    const newPlot = [...input.plot];
    newPlot[idx] = val;
    onChangeInput({ ...input, plot: newPlot });
  };

  const handleSetbackChange = (side, value) => {
    const val = Math.max(0, parseInt(value, 10) || 0);
    onChangeInput({
      ...input,
      setbacks: { ...input.setbacks, [side]: val },
    });
  };

  const handleAddRoom = () => {
    const roomCount = input.rooms.length + 1;
    const newRoom = {
      name: `bedroom ${roomCount > 4 ? 2 : roomCount}`,
      type: 'bedroom',
      zone: 'NE',
      zone_mode: 'try',
    };
    onChangeInput({
      ...input,
      rooms: [...input.rooms, newRoom],
    });
  };

  const handleRemoveRoom = (index) => {
    const updated = input.rooms.filter((_, i) => i !== index);
    onChangeInput({ ...input, rooms: updated });
  };

  const handleRoomFieldChange = (index, field, value) => {
    const updated = input.rooms.map((room, i) => {
      if (i === index) {
        return { ...room, [field]: value };
      }
      return room;
    });
    onChangeInput({ ...input, rooms: updated });
  };

  const handleSelectPreset = (presetId) => {
    setSelectedPresetId(presetId);
    const found = TEST_INPUTS.find((p) => p.id === presetId);
    if (found) {
      onChangeInput(JSON.parse(JSON.stringify(found.input)));
    }
  };

  return (
    <aside className="cad-left-panel">
      <div className="cad-panel-tabs">
        <button
          type="button"
          className={`panel-tab-btn ${activeTab === 'site' ? 'active' : ''}`}
          onClick={() => onSelectTab('site')}
        >
          <Sliders size={13} /> Site &amp; Plot
        </button>
        <button
          type="button"
          className={`panel-tab-btn ${activeTab === 'rooms' ? 'active' : ''}`}
          onClick={() => onSelectTab('rooms')}
        >
          <Layers size={13} /> Rooms ({input.rooms.length})
        </button>
        <button
          type="button"
          className={`panel-tab-btn ${activeTab === 'furniture' ? 'active' : ''}`}
          onClick={() => onSelectTab('furniture')}
        >
          <Box size={13} /> Furniture
        </button>
      </div>

      <div className="cad-panel-content">
        {activeTab === 'site' && (
          <div className="tab-pane">
            <div className="form-group">
              <label className="field-title">Shared Test Preset (10 MVP Gates)</label>
              <select
                className="cad-input-select"
                value={selectedPresetId}
                onChange={(e) => handleSelectPreset(e.target.value)}
              >
                {TEST_INPUTS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="field-title">Plot Dimensions (ft)</label>
              <div className="input-row-2col">
                <div>
                  <span className="field-hint">Width</span>
                  <input
                    type="number"
                    min="10"
                    max="100"
                    className="cad-input-num"
                    value={input.plot[0]}
                    onChange={(e) => handlePlotChange(0, e.target.value)}
                  />
                </div>
                <div>
                  <span className="field-hint">Length</span>
                  <input
                    type="number"
                    min="10"
                    max="100"
                    className="cad-input-num"
                    value={input.plot[1]}
                    onChange={(e) => handlePlotChange(1, e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div className="form-group">
              <label className="field-title">Setbacks (ft)</label>
              <div className="input-row-4col">
                {['front', 'back', 'left', 'right'].map((side) => (
                  <div key={side}>
                    <span className="field-hint">{side.toUpperCase()}</span>
                    <input
                      type="number"
                      min="0"
                      max="30"
                      className="cad-input-num-compact"
                      value={input.setbacks?.[side] ?? 3}
                      onChange={(e) => handleSetbackChange(side, e.target.value)}
                    />
                  </div>
                ))}
              </div>
              <div className="buildable-calc-badge">
                Buildable Envelope: {buildable.width}' × {buildable.length}' ({buildable.area} sq ft)
              </div>
            </div>

            <div className="form-group">
              <div className="input-row-2col">
                <div>
                  <label className="field-title">Entrance Wall</label>
                  <select
                    className="cad-input-select"
                    value={input.entrance || 'S'}
                    onChange={(e) => onChangeInput({ ...input, entrance: e.target.value })}
                  >
                    <option value="S">South (Front)</option>
                    <option value="N">North (Back)</option>
                    <option value="E">East (Right)</option>
                    <option value="W">West (Left)</option>
                  </select>
                </div>
                <div>
                  <label className="field-title">North Orientation</label>
                  <select
                    className="cad-input-select"
                    value={input.north || 'up'}
                    onChange={(e) => onChangeInput({ ...input, north: e.target.value })}
                  >
                    <option value="up">Up (North)</option>
                    <option value="right">Right (East)</option>
                    <option value="down">Down (South)</option>
                    <option value="left">Left (West)</option>
                  </select>
                </div>
              </div>
            </div>

            <div className={`cad-feasibility-card ${feasibility.feasible ? 'ok' : 'fail'}`}>
              {feasibility.feasible ? (
                <div>
                  <div className="feasi-head ok"><CheckCircle2 size={13} /> Buildable Feasibility OK</div>
                  <div className="feasi-sub">Required {feasibility.totalRequiredArea} sq ft vs Buildable {feasibility.buildableArea} sq ft</div>
                </div>
              ) : (
                <div>
                  <div className="feasi-head fail"><AlertCircle size={13} /> Infeasible Plot Shortfall</div>
                  <div className="feasi-sub">Shortfall of {feasibility.shortfall} sq ft. Increase plot size or reduce rooms.</div>
                </div>
              )}
            </div>

            <button
              type="button"
              className="btn-cad-primary"
              onClick={onSolve}
              disabled={isSolving}
            >
              <Sparkles size={14} />
              <span>{isSolving ? 'Solving Layouts...' : 'Solve Layouts (CP-SAT)'}</span>
            </button>
          </div>
        )}

        {activeTab === 'rooms' && (
          <div className="tab-pane">
            <div className="tab-pane-header">
              <span className="field-title">Room Requests ({input.rooms.length}/10)</span>
              <button
                type="button"
                className="btn-add-room-chip"
                onClick={handleAddRoom}
                disabled={input.rooms.length >= 10}
              >
                <Plus size={12} /> Add Room
              </button>
            </div>

            <div className="cad-room-rows-list">
              {input.rooms.map((room, idx) => (
                <div key={idx} className="cad-room-input-card">
                  <div className="room-card-top">
                    <input
                      type="text"
                      className="room-name-field"
                      value={room.name}
                      onChange={(e) => handleRoomFieldChange(idx, 'name', e.target.value)}
                      placeholder="Room name"
                    />
                    <button
                      type="button"
                      className="btn-remove-icon"
                      onClick={() => handleRemoveRoom(idx)}
                      title="Remove room"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>

                  <div className="room-card-bottom">
                    <select
                      className="room-select-type"
                      value={room.type}
                      onChange={(e) => handleRoomFieldChange(idx, 'type', e.target.value)}
                    >
                      {Object.keys(ROOM_SIZE_TABLE).map((t) => (
                        <option key={t} value={t}>
                          {t.charAt(0).toUpperCase() + t.slice(1)}
                        </option>
                      ))}
                    </select>

                    <select
                      className="room-select-zone"
                      value={room.zone || ''}
                      onChange={(e) => handleRoomFieldChange(idx, 'zone', e.target.value || null)}
                    >
                      <option value="">Zone: Any</option>
                      {ZONES.map((z) => (
                        <option key={z} value={z}>{z}</option>
                      ))}
                    </select>

                    <select
                      className="room-select-mode"
                      value={room.zone_mode || 'try'}
                      onChange={(e) => handleRoomFieldChange(idx, 'zone_mode', e.target.value)}
                    >
                      <option value="try">Try</option>
                      <option value="must">Must</option>
                    </select>
                  </div>
                </div>
              ))}
            </div>

            <button
              type="button"
              className="btn-cad-primary"
              onClick={onSolve}
              disabled={isSolving}
            >
              <Sparkles size={14} />
              <span>{isSolving ? 'Solving Layouts...' : 'Solve Layouts'}</span>
            </button>
          </div>
        )}

        {activeTab === 'furniture' && (
          <div className="tab-pane">
            <div className="tab-pane-header">
              <span className="field-title">Furniture Library</span>
              <button
                type="button"
                className="btn-add-room-chip"
                onClick={onAutoFurnish}
              >
                <Sparkles size={12} /> Auto-Furnish
              </button>
            </div>

            <div className="furniture-cat-bar">
              {['all', 'bedroom', 'living', 'kitchen', 'bathroom', 'study'].map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`furn-cat-btn ${furnitureCategory === c ? 'active' : ''}`}
                  onClick={() => setFurnitureCategory(c)}
                >
                  {c.charAt(0).toUpperCase() + c.slice(1)}
                </button>
              ))}
            </div>

            <div className="furniture-library-grid">
              {filteredFurniture.map((item) => (
                <div
                  key={item.id}
                  className="cad-furn-card"
                  onClick={() => onAddFurnitureItem && onAddFurnitureItem(item)}
                  title={`Place ${item.name}`}
                >
                  <div className="furn-card-icon">
                    {item.category === 'bedroom' && <Bed size={16} />}
                    {item.category === 'living' && <Armchair size={16} />}
                    {item.category === 'kitchen' && <Utensils size={16} />}
                    {item.category === 'bathroom' && <Bath size={16} />}
                    {item.category === 'study' && <Briefcase size={16} />}
                    {item.category === 'dining' && <Utensils size={16} />}
                  </div>
                  <div className="furn-card-info">
                    <span className="furn-card-name">{item.name}</span>
                    <span className="furn-card-dim">{item.w}' × {item.h}'</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
