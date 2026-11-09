import React, { useState } from 'react';
import { 
  Compass, 
  Layers, 
  Sliders, 
  Download, 
  FileText, 
  Cpu, 
  Server,
  BookOpen,
  ChevronDown,
  Maximize2,
  Grid,
  Eye,
  Sparkles,
  RotateCcw,
  RotateCw,
  Box
} from 'lucide-react';
import { SQFT_TO_SQM } from '../engine/materials';

export default function Header({
  layout,
  layouts = [],
  activeLayoutId,
  onSelectLayout,
  unitSystem = 'imperial',
  onToggleUnits,
  showGrid = true,
  onToggleGrid,
  showDoors = true,
  onToggleDoors,
  showWindows = true,
  onToggleWindows,
  showDimensions = true,
  onToggleDimensions,
  showFurniture = true,
  onToggleFurniture,
  showLabels = true,
  onToggleLabels,
  onDownloadSvg,
  onDownloadJson,
  onOpenRoomTable,
  useBackend,
  onToggleBackend,
  engineSource,
  onUndo,
  onRedo,
}) {
  const [isFileMenuOpen, setIsFileMenuOpen] = useState(false);

  const totalNetSqft = layout?.rooms?.reduce((acc, r) => acc + (r.w * r.h), 0) || 0;
  const totalNetSqm = Math.round(totalNetSqft * SQFT_TO_SQM * 10) / 10;

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  return (
    <header className="cad-header">
      <div className="cad-header-left">
        <div className="cad-logo-group">
          <div className="cad-logo-icon">
            <Layers size={18} />
          </div>
          <div className="cad-title-box">
            <div className="cad-brand-name">
              PlanCraft <span className="cad-badge">2D CAD</span>
            </div>
            <div className="cad-subtitle">
              {unitSystem === 'imperial' 
                ? `${totalNetSqft} sq ft · Scale 1:50 · Precision 1 ft grid`
                : `${totalNetSqm} m² · Scale 1:50 · Precision 0.3m grid`}
            </div>
          </div>
        </div>

        <div className="archetype-selector-tabs">
          {layouts.map((l) => (
            <button
              key={l.id}
              type="button"
              className={`archetype-tab ${l.id === activeLayoutId ? 'active' : ''}`}
              onClick={() => onSelectLayout(l.id)}
            >
              <span className="arch-name">{l.archetype}</span>
              <span className="arch-score">Score: {l.score}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="cad-header-center">
        <div className="cad-layer-controls">
          <button
            type="button"
            className={`layer-chip ${showGrid ? 'active' : ''}`}
            onClick={onToggleGrid}
            title="Toggle Drafting Grid"
          >
            <Grid size={13} /> Grid
          </button>
          <button
            type="button"
            className={`layer-chip ${showDoors ? 'active' : ''}`}
            onClick={onToggleDoors}
            title="Toggle Doors & Swing Arcs"
          >
            Doors
          </button>
          <button
            type="button"
            className={`layer-chip ${showWindows ? 'active' : ''}`}
            onClick={onToggleWindows}
            title="Toggle Window Glazing"
          >
            Windows
          </button>
          <button
            type="button"
            className={`layer-chip ${showFurniture ? 'active' : ''}`}
            onClick={onToggleFurniture}
            title="Toggle Furniture Layout"
          >
            <Box size={13} /> Furniture
          </button>
          <button
            type="button"
            className={`layer-chip ${showDimensions ? 'active' : ''}`}
            onClick={onToggleDimensions}
            title="Toggle Dimension Ticks"
          >
            Dimensions
          </button>
          <button
            type="button"
            className={`layer-chip ${showLabels ? 'active' : ''}`}
            onClick={onToggleLabels}
            title="Toggle Room Area Labels"
          >
            Labels
          </button>
        </div>

        <div className="history-quick-btns">
          <button type="button" className="cad-mini-btn" onClick={onUndo} title="Undo">
            <RotateCcw size={13} />
          </button>
          <button type="button" className="cad-mini-btn" onClick={onRedo} title="Redo">
            <RotateCw size={13} />
          </button>
        </div>
      </div>

      <div className="cad-header-right">
        <button
          type="button"
          className="unit-toggle-btn"
          onClick={onToggleUnits}
          title="Toggle Imperial (ft) / Metric (m)"
        >
          {unitSystem === 'imperial' ? 'FT / SQ FT' : 'M / M²'}
        </button>

        <div className="engine-status-pill" onClick={onToggleBackend} title="Toggle Local Engine vs FastAPI Backend">
          {useBackend ? (
            <span className="status-label backend">
              <Server size={12} /> FastAPI (P3)
            </span>
          ) : (
            <span className="status-label local">
              <Cpu size={12} /> Local CAD (P5)
            </span>
          )}
        </div>

        <button
          type="button"
          className="cad-action-btn"
          onClick={toggleFullscreen}
          title="Fullscreen"
        >
          <Maximize2 size={14} />
        </button>

        <div className="file-dropdown-wrapper">
          <button
            type="button"
            className="file-trigger-btn"
            onClick={() => setIsFileMenuOpen(!isFileMenuOpen)}
          >
            <span>Export</span>
            <ChevronDown size={13} />
          </button>

          {isFileMenuOpen && (
            <div className="cad-dropdown-menu" onMouseLeave={() => setIsFileMenuOpen(false)}>
              <button
                type="button"
                className="cad-dropdown-item"
                onClick={() => {
                  onDownloadSvg();
                  setIsFileMenuOpen(false);
                }}
              >
                <Download size={13} /> Export Vector SVG
              </button>
              <button
                type="button"
                className="cad-dropdown-item"
                onClick={() => {
                  onDownloadJson();
                  setIsFileMenuOpen(false);
                }}
              >
                <FileText size={13} /> Export Floorplan JSON
              </button>
              <div className="cad-dropdown-sep" />
              <button
                type="button"
                className="cad-dropdown-item"
                onClick={() => {
                  onOpenRoomTable();
                  setIsFileMenuOpen(false);
                }}
              >
                <BookOpen size={13} /> Room Size Table
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
