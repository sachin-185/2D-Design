import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import Canvas from './components/Canvas';
import LeftSidebar from './components/LeftSidebar';
import RightSidebar from './components/RightSidebar';
import RoomSizeTableModal from './components/RoomSizeTableModal';
import { TEST_INPUTS } from './engine/testInputs';
import { requestGenerate } from './engine/apiClient';
import { generateAutoFurniture } from './engine/furniture';

export default function App() {
  const [input, setInput] = useState(TEST_INPUTS[0].input);
  const [layouts, setLayouts] = useState([]);
  const [activeLayoutId, setActiveLayoutId] = useState(null);
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [feasibility, setFeasibility] = useState(null);
  const [problems, setProblems] = useState([]);
  const [messages, setMessages] = useState([]);
  const [apiError, setApiError] = useState(null);
  const [isSolving, setIsSolving] = useState(false);
  const [useBackend, setUseBackend] = useState(false);
  const [engineSource, setEngineSource] = useState('local-engine');

  const [activeLeftTab, setActiveLeftTab] = useState('site');
  const [unitSystem, setUnitSystem] = useState('imperial');

  const [showGrid, setShowGrid] = useState(true);
  const [showDoors, setShowDoors] = useState(true);
  const [showWindows, setShowWindows] = useState(true);
  const [showFurniture, setShowFurniture] = useState(true);
  const [showDimensions, setShowDimensions] = useState(true);
  const [showLabels, setShowLabels] = useState(true);

  const [furniture, setFurniture] = useState([]);
  const [customRoomFlooring, setCustomRoomFlooring] = useState({});

  const [history, setHistory] = useState([]);
  const [historyIndex, setHistoryIndex] = useState(-1);

  const [isRoomTableOpen, setIsRoomTableOpen] = useState(false);

  const activeLayout = layouts.find((l) => l.id === activeLayoutId) || layouts[0] || null;

  useEffect(() => {
    if (activeLayout && activeLayout.rooms) {
      const autoItems = generateAutoFurniture(activeLayout.rooms);
      setFurniture(autoItems);
    } else {
      setFurniture([]);
    }
  }, [activeLayout?.id, activeLayout?.rooms?.length]);

  const pushHistory = (newInput) => {
    setHistory((prev) => {
      const next = prev.slice(0, historyIndex + 1);
      return [...next, JSON.parse(JSON.stringify(newInput))];
    });
    setHistoryIndex((prev) => prev + 1);
  };

  const executeSolve = useCallback(async (customInput) => {
    const currentInput = customInput || input;
    setIsSolving(true);
    setApiError(null);

    try {
      const response = await requestGenerate(currentInput, useBackend);
      const data = response.data;

      setLayouts(data.layouts || []);
      setFeasibility(data.feasibility || null);
      setProblems(data.problems || []);
      setMessages(data.messages || []);
      setEngineSource(response.source);

      if (data.layouts && data.layouts.length > 0) {
        setActiveLayoutId((prev) => {
          const exists = data.layouts.some((l) => l.id === prev);
          return exists ? prev : data.layouts[0].id;
        });

        if (selectedRoom) {
          const match = data.layouts[0].rooms.find((r) => r.name === selectedRoom.name);
          setSelectedRoom(match || null);
        }
      } else {
        setActiveLayoutId(null);
        setSelectedRoom(null);
      }
    } catch (err) {
      console.error('Solve failed:', err);
      setApiError(err.message);
      setLayouts([]);
      setActiveLayoutId(null);
      setSelectedRoom(null);
      setProblems([
        {
          code: 'I1',
          message: err.message,
          rooms: [],
          severity: 'error',
        },
      ]);
    } finally {
      setIsSolving(false);
    }
  }, [input, useBackend, selectedRoom]);

  useEffect(() => {
    executeSolve(TEST_INPUTS[0].input);
    pushHistory(TEST_INPUTS[0].input);
  }, []);

  const handleSelectRoom = (room) => {
    setSelectedRoom(room);
  };

  const handleApplyPin = (pinData) => {
    let existingPins = input.pins ? [...input.pins] : [];

    if (pinData.clear) {
      existingPins = pinData.remaining || [];
    } else {
      const index = existingPins.findIndex((p) => p.room === pinData.room);
      if (index >= 0) {
        existingPins[index] = pinData;
      } else {
        existingPins.push(pinData);
      }
    }

    const updatedInput = { ...input, pins: existingPins };
    setInput(updatedInput);
    pushHistory(updatedInput);
    executeSolve(updatedInput);
  };

  const handleChangeInput = (newInput) => {
    setInput(newInput);
    setSelectedRoom(null);
    setApiError(null);
    pushHistory(newInput);
  };

  const handleUndo = () => {
    if (historyIndex > 0) {
      const prevInput = history[historyIndex - 1];
      setHistoryIndex(historyIndex - 1);
      setInput(prevInput);
      executeSolve(prevInput);
    }
  };

  const handleRedo = () => {
    if (historyIndex < history.length - 1) {
      const nextInput = history[historyIndex + 1];
      setHistoryIndex(historyIndex + 1);
      setInput(nextInput);
      executeSolve(nextInput);
    }
  };

  const handleDownloadSvg = () => {
    const svgEl = document.querySelector('.cad-svg-sheet');
    if (!svgEl) return;
    const serializer = new XMLSerializer();
    const source = serializer.serializeToString(svgEl);
    const blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `plancraft-${activeLayout?.archetype || 'draft'}.svg`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadJson = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(input, null, 2));
    const link = document.createElement('a');
    link.href = dataStr;
    link.download = 'floorplan-spec.json';
    link.click();
  };

  const handleAddFurnitureItem = (catalogItem) => {
    if (!activeLayout?.rooms || activeLayout.rooms.length === 0) return;
    const targetRoom = selectedRoom || activeLayout.rooms[0];

    const newItem = {
      id: `furn-${Date.now()}`,
      catalogId: catalogItem.id,
      roomName: targetRoom.name,
      name: catalogItem.name,
      x: targetRoom.x + targetRoom.w / 2 - catalogItem.w / 2,
      y: targetRoom.y + targetRoom.h / 2 - catalogItem.h / 2,
      w: catalogItem.w,
      h: catalogItem.h,
      color: catalogItem.color,
      accentColor: catalogItem.accentColor,
      type: catalogItem.category,
    };

    setFurniture((prev) => [...prev, newItem]);
  };

  const handleAutoFurnish = () => {
    if (activeLayout?.rooms) {
      setFurniture(generateAutoFurniture(activeLayout.rooms));
    }
  };

  return (
    <div className="cad-studio-container">
      <Header
        layout={activeLayout}
        layouts={layouts}
        activeLayoutId={activeLayoutId}
        onSelectLayout={(id) => {
          setActiveLayoutId(id);
          setSelectedRoom(null);
        }}
        unitSystem={unitSystem}
        onToggleUnits={() => setUnitSystem(unitSystem === 'imperial' ? 'metric' : 'imperial')}
        showGrid={showGrid}
        onToggleGrid={() => setShowGrid(!showGrid)}
        showDoors={showDoors}
        onToggleDoors={() => setShowDoors(!showDoors)}
        showWindows={showWindows}
        onToggleWindows={() => setShowWindows(!showWindows)}
        showDimensions={showDimensions}
        onToggleDimensions={() => setShowDimensions(!showDimensions)}
        showFurniture={showFurniture}
        onToggleFurniture={() => setShowFurniture(!showFurniture)}
        showLabels={showLabels}
        onToggleLabels={() => setShowLabels(!showLabels)}
        onDownloadSvg={handleDownloadSvg}
        onDownloadJson={handleDownloadJson}
        onOpenRoomTable={() => setIsRoomTableOpen(true)}
        useBackend={useBackend}
        onToggleBackend={() => setUseBackend(!useBackend)}
        engineSource={engineSource}
        onUndo={handleUndo}
        onRedo={handleRedo}
      />

      <main className="cad-studio-main">
        <LeftSidebar
          activeTab={activeLeftTab}
          onSelectTab={setActiveLeftTab}
          layout={activeLayout}
          input={input}
          onChangeInput={handleChangeInput}
          onSolve={() => executeSolve(input)}
          isSolving={isSolving}
          onAddFurnitureItem={handleAddFurnitureItem}
          onAutoFurnish={handleAutoFurnish}
        />

        <div className="cad-workbench-area">
          {activeLayout ? (
            <Canvas layout={activeLayout}
              input={input} selectedRoom={selectedRoom}
              onSelectRoom={handleSelectRoom}
              furniture={furniture} showGrid={showGrid}
              showDoors={showDoors}
              showWindows={showWindows} showFurniture={showFurniture}
              showDimensions={showDimensions}
              showLabels={showLabels} unitSystem={unitSystem} />
          ) : (
            <div className="cad-empty-sheet">
              <div className="cad-empty-message">
                <h3>Drafting Solution Infeasible</h3>
                <p>{apiError || 'The plot dimensions are too small to satisfy the room area requirements and circulation.'}</p>
                <button
                  type="button"
                  className="btn-cad-primary"
                  onClick={() => executeSolve(TEST_INPUTS[0].input)}
                >
                  Load Standard 4-Room Preset
                </button>
              </div>
            </div>
          )}
        </div>

        <RightSidebar
          layout={activeLayout}
          input={input}
          selectedRoom={selectedRoom}
          onSelectRoom={handleSelectRoom}
          onApplyPin={handleApplyPin}
          unitSystem={unitSystem}
          customRoomFlooring={customRoomFlooring}
          onChangeRoomFlooring={(roomName, matId) => {
            setCustomRoomFlooring((prev) => ({ ...prev, [roomName]: matId }));
          }}
          problems={problems}
        />
      </main>

      <RoomSizeTableModal
        isOpen={isRoomTableOpen}
        onClose={() => setIsRoomTableOpen(false)}
      />
    </div>
  );
}
