import React, { useState, useEffect, useCallback, useRef } from 'react';
import Header from './components/Header';
import Canvas from './components/Canvas';
import LeftSidebar from './components/LeftSidebar';
import RightSidebar from './components/RightSidebar';
import RoomSizeTableModal from './components/RoomSizeTableModal';
import { TEST_INPUTS } from './engine/testInputs';
import { requestGenerate, requestEdit } from './engine/apiClient';
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
  // The real engine (FastAPI backend) is the default; the header pill switches to the offline demo solver.
  const [useBackend, setUseBackend] = useState(true);
  const [engineSource, setEngineSource] = useState('backend-api');

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

  // The input the plans on screen were solved for. Plans are always drawn with this input, so changing a
  // field (or picking a preset) can never draw old rooms inside a new plot.
  const [solvedInput, setSolvedInput] = useState(null);
  const latestRequest = useRef(0); // a slow older answer must not replace a newer one
  const inputChanged = solvedInput !== null && JSON.stringify(solvedInput) !== JSON.stringify(input);

  const activeLayout = layouts.find((l) => l.id === activeLayoutId) || layouts[0] || null;

  // Re-furnish whenever room positions change, not only when the layout id or room count changes.
  const roomsKey = (activeLayout?.rooms || []).map((r) => `${r.name}:${r.x},${r.y},${r.w},${r.h}`).join('|');
  useEffect(() => {
    if (activeLayout && activeLayout.rooms) {
      const autoItems = generateAutoFurniture(activeLayout.rooms);
      setFurniture(autoItems);
    } else {
      setFurniture([]);
    }
  }, [activeLayout?.id, roomsKey]);

  const pushHistory = (newInput) => {
    setHistory((prev) => {
      const next = prev.slice(0, historyIndex + 1);
      return [...next, JSON.parse(JSON.stringify(newInput))];
    });
    setHistoryIndex((prev) => prev + 1);
  };

  const executeSolve = useCallback(async (customInput) => {
    const currentInput = customInput || input;
    const requestId = ++latestRequest.current;
    setIsSolving(true);
    setApiError(null);

    try {
      const response = await requestGenerate(currentInput, useBackend);
      if (requestId !== latestRequest.current) return; // a newer solve was started meanwhile
      const data = response.data;

      setSolvedInput(currentInput);
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
      if (requestId !== latestRequest.current) return;
      console.error('Solve failed:', err);
      setApiError(err.message);
      setSolvedInput(currentInput);
      setLayouts([]);
      setActiveLayoutId(null);
      setSelectedRoom(null);
      setMessages([]);
      setProblems([
        {
          code: err.errorCode || err.status || 'I1',
          message: err.message,
          rooms: [],
          severity: 'error',
        },
      ]);
    } finally {
      if (requestId === latestRequest.current) setIsSolving(false);
    }
  }, [input, useBackend, selectedRoom]);

  useEffect(() => {
    executeSolve(TEST_INPUTS[0].input);
    pushHistory(TEST_INPUTS[0].input);
  }, []);

  const handleSelectRoom = (room) => {
    setSelectedRoom(room);
  };

  // Backend edit: only the changed sizes are sent; the other plans stay as they are.
  const applyBackendEdit = async (pinData) => {
    const current = activeLayout.rooms.find((r) => r.name === pinData.room);
    const edits = {};
    if (pinData.width && pinData.width !== current?.w) edits.width = pinData.width;
    if (pinData.height && pinData.height !== current?.h) edits.height = pinData.height;

    const otherPins = (input.pins || []).filter((p) => p.room !== pinData.room);
    if (Object.keys(edits).length === 0) {
      // Only the lock changed: remember it for the next edit, no re-solve needed.
      const pin = { ...(input.pins || []).find((p) => p.room === pinData.room), room: pinData.room };
      if (pinData.locked) pin.locked = true; else delete pin.locked;
      const keep = Object.keys(pin).length > 1 ? [pin] : [];
      const updatedInput = { ...input, pins: [...otherPins, ...keep] };
      setInput(updatedInput);
      setSolvedInput(updatedInput); // a lock does not change the plan on screen
      pushHistory(updatedInput);
      return;
    }

    const requestId = ++latestRequest.current;
    setIsSolving(true);
    setApiError(null);
    try {
      const lock = otherPins.filter((p) => p.locked).map((p) => p.room);
      // The room being resized cannot also stay frozen, so its own lock is not sent.
      const sentInput = {
        ...input,
        pins: (input.pins || []).map((p) => {
          if (p.room !== pinData.room) return p;
          const { locked, ...rest } = p;
          return rest;
        }),
      };
      const response = await requestEdit(sentInput, activeLayout, { [pinData.room]: edits }, lock);
      if (requestId !== latestRequest.current) return;
      const edited = response.data.layouts[0];
      const updatedInput = response.data.input || input;
      if (pinData.locked) {
        // The engine unlocks a room that was just edited; keep the user's lock for later edits.
        updatedInput.pins = updatedInput.pins.map((p) => (p.room === pinData.room ? { ...p, locked: true } : p));
      }
      setLayouts((prev) => prev.map((l) => (l.id === activeLayout.id
        ? { ...edited, id: l.id, variantNumber: l.variantNumber, archetype: `${l.archetype.replace(/ \(edited\)$/, '')} (edited)` }
        : l)));
      setInput(updatedInput);
      setSolvedInput(updatedInput);
      pushHistory(updatedInput);
      setMessages(response.data.messages || []);
      setProblems(response.data.problems || []);
      setEngineSource(response.source);
      setSelectedRoom(edited.rooms.find((r) => r.name === pinData.room) || null);
    } catch (err) {
      if (requestId !== latestRequest.current) return;
      // Keep the current plans on screen and explain why the edit cannot be built.
      setProblems([{ code: err.errorCode || 'EDIT', message: err.message, rooms: [pinData.room], severity: 'error' }]);
    } finally {
      if (requestId === latestRequest.current) setIsSolving(false);
    }
  };

  const handleApplyPin = (pinData) => {
    if (inputChanged && !pinData.clear) {
      // The plan on screen belongs to the old input; editing it against the new input would mix the two.
      setProblems([{ code: 'STALE', message: 'The inputs changed since this plan was solved. Press Solve Layouts first.',
        rooms: [], severity: 'error' }]);
      return;
    }
    if (useBackend && activeLayout && !pinData.clear) {
      applyBackendEdit(pinData);
      return;
    }
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

  // options.solve: solve at once (used when a preset is picked, since the old plan no longer applies).
  const handleChangeInput = (newInput, options = {}) => {
    setInput(newInput);
    setSelectedRoom(null);
    setApiError(null);
    pushHistory(newInput);
    if (options.solve) executeSolve(newInput);
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
        onRedo={handleRedo} />

      <main className="cad-studio-main">
        <LeftSidebar activeTab={activeLeftTab} onSelectTab={setActiveLeftTab}
          layout={activeLayout} input={input} onChangeInput={handleChangeInput}
          onSolve={() => executeSolve(input)} isSolving={isSolving}
          onAddFurnitureItem={handleAddFurnitureItem}
          onAutoFurnish={handleAutoFurnish} />

        <div className="cad-workbench-area">
          {(inputChanged || isSolving) && (
            <div className={`cad-stale-banner ${isSolving ? 'solving' : ''}`}>
              {isSolving ? (
                <span>Solving layouts…</span>
              ) : (
                <>
                  <span>Inputs changed. The drawing still shows the last solved plan.</span>
                  <button type="button" className="btn-cad-primary" onClick={() => executeSolve(input)}>
                    Solve now
                  </button>
                </>
              )}
            </div>
          )}
          {activeLayout ? (
            // Drawn with the input it was solved for, never with newer unsolved input.
            <Canvas layout={activeLayout}
              input={solvedInput || input} selectedRoom={selectedRoom} onSelectRoom={handleSelectRoom}
              furniture={furniture} showGrid={showGrid} showDoors={showDoors}
              showWindows={showWindows} showFurniture={showFurniture}
              showDimensions={showDimensions} showLabels={showLabels} unitSystem={unitSystem} />
          ) : (
            <div className="cad-empty-sheet">
              <div className="cad-empty-message">
                {isSolving || !solvedInput ? (
                  <h3>Solving layouts…</h3>
                ) : (
                  <>
                    <h3>No layout for these inputs</h3>
                    <p>{apiError || 'The plot dimensions are too small to satisfy the room area requirements and circulation.'}</p>
                    <button type="button" className="btn-cad-primary"
                      onClick={() => handleChangeInput(JSON.parse(JSON.stringify(TEST_INPUTS[0].input)), { solve: true })}>
                      Load Standard 4-Room Preset
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        <RightSidebar layout={activeLayout} input={input} selectedRoom={selectedRoom} onSelectRoom={handleSelectRoom}
          onApplyPin={handleApplyPin} unitSystem={unitSystem} customRoomFlooring={customRoomFlooring}
          onChangeRoomFlooring={(roomName, matId) => {
            setCustomRoomFlooring((prev) => ({ ...prev, [roomName]: matId }));
          }}
          problems={[
            ...problems,
            // engine notes for the plan on screen, e.g. a relaxed zone preference or no hallway
            ...(activeLayout?.messages || [])
              .filter((m) => !m.startsWith('Warning'))
              .map((m) => ({ code: 'Note', message: m, rooms: [], severity: 'info' })),
            ...messages.map((m) => ({ code: 'Note', message: m, rooms: [], severity: 'info' })),
          ]} />
      </main>

      <RoomSizeTableModal isOpen={isRoomTableOpen} onClose={() => setIsRoomTableOpen(false)} />
    </div>
  );
}
