import React, { useState } from 'react';
import { 
  Plus, 
  Trash2, 
  Sliders, 
  Sparkles, 
  AlertCircle, 
  CheckCircle2, 
  BookOpen, 
  RefreshCw,
  Link2
} from 'lucide-react';
import { ROOM_SIZE_TABLE, ZONES, checkFeasibility } from '../engine/contracts';
import { TEST_INPUTS } from '../engine/testInputs';

export default function InputForm({ 
  input, 
  onChangeInput, 
  onSolve, 
  isLoading, 
  onOpenRoomTable 
}) {
  const [selectedPresetId, setSelectedPresetId] = useState('test-1-standard');

  const feasibility = checkFeasibility(input.plot, input.setbacks, input.rooms);

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
        const next = { ...room, [field]: value };
        if (field === 'type' && value !== 'bathroom') {
          delete next.attached_to;
        }
        return next;
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

  const bedroomNames = input.rooms
    .filter((r) => r.type === 'bedroom')
    .map((r) => r.name);

  return (
    <div className="input-form-card">
      <div className="form-header">
        <div className="form-header-title">
          <Sliders size={18} className="text-cyan" />
          <h3>Project &amp; Room Inputs</h3>
        </div>
        <button 
          type="button" 
          className="btn-text-subtle" 
          onClick={onOpenRoomTable}
          title="View standard minimum, preferred, and maximum dimensions"
        >
          <BookOpen size={14} /> Room Table
        </button>
      </div>

      <div className="form-section">
        <label className="field-label">Load Shared Test Preset (10 MVP Inputs):</label>
        <select 
          className="custom-select" 
          value={selectedPresetId}
          onChange={(e) => handleSelectPreset(e.target.value)}
        >
          {TEST_INPUTS.map((t) => (
            <option key={t.id} value={t.id}>
              {t.title}
            </option>
          ))}
        </select>
      </div>

      <div className="form-section">
        <label className="field-label">Plot Dimensions (ft, 1ft grid):</label>
        <div className="grid-2col">
          <div className="input-wrapper">
            <span className="input-prefix">W:</span>
            <input
              type="number"
              min="15"
              max="100"
              value={input.plot[0]}
              onChange={(e) => handlePlotChange(0, e.target.value)}
              className="number-input"
            />
            <span className="input-unit">ft</span>
          </div>
          <div className="input-wrapper">
            <span className="input-prefix">L:</span>
            <input
              type="number"
              min="15"
              max="100"
              value={input.plot[1]}
              onChange={(e) => handlePlotChange(1, e.target.value)}
              className="number-input"
            />
            <span className="input-unit">ft</span>
          </div>
        </div>
      </div>

      <div className="form-section">
        <label className="field-label">Setbacks (ft):</label>
        <div className="grid-4col">
          <div className="setback-box">
            <span className="sub-label">Front (S)</span>
            <input
              type="number"
              min="0"
              max="20"
              value={input.setbacks.front}
              onChange={(e) => handleSetbackChange('front', e.target.value)}
              className="mini-input"
            />
          </div>
          <div className="setback-box">
            <span className="sub-label">Back (N)</span>
            <input
              type="number"
              min="0"
              max="20"
              value={input.setbacks.back}
              onChange={(e) => handleSetbackChange('back', e.target.value)}
              className="mini-input"
            />
          </div>
          <div className="setback-box">
            <span className="sub-label">Left (W)</span>
            <input
              type="number"
              min="0"
              max="20"
              value={input.setbacks.left}
              onChange={(e) => handleSetbackChange('left', e.target.value)}
              className="mini-input"
            />
          </div>
          <div className="setback-box">
            <span className="sub-label">Right (E)</span>
            <input
              type="number"
              min="0"
              max="20"
              value={input.setbacks.right}
              onChange={(e) => handleSetbackChange('right', e.target.value)}
              className="mini-input"
            />
          </div>
        </div>
      </div>

      <div className="form-section grid-2col">
        <div>
          <label className="field-label">Entrance Side:</label>
          <select
            className="custom-select"
            value={input.entrance || 'S'}
            onChange={(e) => onChangeInput({ ...input, entrance: e.target.value })}
          >
            <option value="S">South (Front, y=0)</option>
            <option value="N">North (Back, y=L)</option>
            <option value="E">East (Right, x=W)</option>
            <option value="W">West (Left, x=0)</option>
          </select>
        </div>
        <div>
          <label className="field-label">North Orientation:</label>
          <select
            className="custom-select"
            value={input.north || 'up'}
            onChange={(e) => onChangeInput({ ...input, north: e.target.value })}
          >
            <option value="up">North (Up)</option>
            <option value="right">North (Right)</option>
            <option value="down">North (Down)</option>
            <option value="left">North (Left)</option>
          </select>
        </div>
      </div>

      <div className={`feasibility-badge ${feasibility.feasible ? 'valid' : 'invalid'}`}>
        {feasibility.feasible ? (
          <>
            <CheckCircle2 size={16} />
            <div>
              <strong>Feasible Plot:</strong> {feasibility.buildableArea} sq ft buildable vs {feasibility.totalRequired} sq ft min required.
            </div>
          </>
        ) : (
          <>
            <AlertCircle size={16} />
            <div>
              <strong>Plot Too Small:</strong> Shortfall of {feasibility.shortfall} sq ft!
            </div>
          </>
        )}
      </div>

      <div className="form-section">
        <div className="section-title-row">
          <label className="field-label">Rooms (Up to 10 rooms):</label>
          <button 
            type="button" 
            className="btn-add-room" 
            onClick={handleAddRoom}
            disabled={input.rooms.length >= 10}
          >
            <Plus size={14} /> Add Room
          </button>
        </div>

        <div className="rooms-form-list">
          {input.rooms.map((room, idx) => (
            <div key={idx} className="room-row-card">
              <div className="room-row-top">
                <input
                  type="text"
                  value={room.name}
                  onChange={(e) => handleRoomFieldChange(idx, 'name', e.target.value)}
                  className="room-name-input"
                  placeholder="Room name"
                />
                <select
                  value={room.type}
                  onChange={(e) => handleRoomFieldChange(idx, 'type', e.target.value)}
                  className="room-type-select"
                >
                  {Object.keys(ROOM_SIZE_TABLE).map((t) => (
                    <option key={t} value={t}>
                      {ROOM_SIZE_TABLE[t].name}
                    </option>
                  ))}
                </select>

                {input.rooms.length > 2 && (
                  <button
                    type="button"
                    className="btn-icon-danger"
                    onClick={() => handleRemoveRoom(idx)}
                    title="Remove room"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>

              {room.type === 'bathroom' && (
                <div className="attached-row">
                  <Link2 size={13} className="text-cyan" />
                  <span className="sub-label">Connection:</span>
                  <select
                    value={room.attached_to || ''}
                    onChange={(e) => handleRoomFieldChange(idx, 'attached_to', e.target.value || undefined)}
                    className="attached-select"
                  >
                    <option value="">Common Bath (Hallway / Living)</option>
                    {bedroomNames.map((bedName) => (
                      <option key={bedName} value={bedName}>
                        Ensuite: Attached to {bedName}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="room-row-bottom">
                <div className="zone-select-group">
                  <span className="zone-label">3x3 Zone:</span>
                  <select
                    value={room.zone || ''}
                    onChange={(e) => handleRoomFieldChange(idx, 'zone', e.target.value || undefined)}
                    className="zone-select"
                  >
                    <option value="">Any Zone</option>
                    {ZONES.map((z) => (
                      <option key={z} value={z}>
                        {z}
                      </option>
                    ))}
                  </select>
                </div>

                {room.zone && (
                  <div className="zone-mode-group">
                    <label className="radio-pill">
                      <input
                        type="radio"
                        name={`mode-${idx}`}
                        value="try"
                        checked={room.zone_mode !== 'must'}
                        onChange={() => handleRoomFieldChange(idx, 'zone_mode', 'try')}
                      />
                      <span>Try</span>
                    </label>
                    <label className="radio-pill must-pill">
                      <input
                        type="radio"
                        name={`mode-${idx}`}
                        value="must"
                        checked={room.zone_mode === 'must'}
                        onChange={() => handleRoomFieldChange(idx, 'zone_mode', 'must')}
                      />
                      <span>Must</span>
                    </label>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <button 
        type="button" 
        className="btn-primary-solve" 
        onClick={onSolve} 
        disabled={isLoading}
      >
        {isLoading ? (
          <>
            <RefreshCw size={18} className="animate-spin" />
            <span>Solving via Engine (Max 10s)...</span>
          </>
        ) : (
          <>
            <Sparkles size={18} />
            <span>Generate Floorplan</span>
          </>
        )}
      </button>
    </div>
  );
}
