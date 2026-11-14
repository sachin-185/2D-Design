import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { checkLayout } from "./checker.js";

const input = {
  plot: [30, 40],
  setbacks: { front: 0, back: 0, left: 0, right: 0 },
  entrance: "S",
  rooms: [
    { name: "living", type: "living" },
    { name: "kitchen", type: "kitchen" },
  ],
};

describe("checker.js - P4 regression tests", () => {
  it("rejects a hallway narrower than 3 ft", () => {
    const layout = {
      rooms: [],
      hallway_segments: [{ id: "hallway_1", x: 0, y: 0, w: 2, h: 12 }],
    };

    const problems = checkLayout(layout, input);

    assert.ok(
      problems.some((p) => p.code === "HW1" && p.severity === "error"),
      "Expected HW1 error for a 2 ft hallway width",
    );
  });

  it("rejects a combined hallway footprint containing a 5x5 square", () => {
    const layout = {
      rooms: [],
      hallway_segments: [
        { id: "hallway_1", x: 0, y: 0, w: 4, h: 12 },
        { id: "hallway_2", x: 2, y: 4, w: 4, h: 12 },
      ],
    };

    const problems = checkLayout(layout, input);

    assert.ok(
      problems.some((p) => p.code === "HW3" && p.severity === "error"),
      "Expected HW3 error because the combined hallway footprint contains a 5x5 square",
    );
  });

  it("does not accept kitchen-to-hallway as a substitute for kitchen-to-living connection", () => {
    const layout = {
      rooms: [
        { name: "living", type: "living", x: 15, y: 0, w: 12, h: 12 },
        { name: "kitchen", type: "kitchen", x: 3, y: 0, w: 8, h: 8 },
      ],
      hallway_segments: [{ id: "hallway_1", x: 0, y: 0, w: 3, h: 12 }],
    };

    const problems = checkLayout(layout, input);

    assert.ok(
      problems.some((p) => p.code === "H6" && p.severity === "error"),
      "Expected H6 error because the kitchen does not connect to the living room",
    );
  });
});

it("continues validation after detecting an HW3 error", () => {
  const layout = {
    rooms: [],
    hallway_segments: [
      { id: "hallway_1", x: 0, y: 0, w: 4, h: 12 },
      { id: "hallway_2", x: 2, y: 4, w: 4, h: 12 },
    ],
  };

  const doors = [{ between: ["living", "kitchen"], width: 2 }];

  const problems = checkLayout(layout, input, doors);

  assert.ok(
    problems.some((p) => p.code === "HW3"),
    "Expected HW3 error",
  );

  assert.ok(
    problems.some((p) => p.code === "F3"),
    "Expected F3 error even after HW3 is detected",
  );
});

it("rejects hallway segments that are disconnected by less than 3 ft", () => {
  const layout = {
    rooms: [],
    hallway_segments: [
      { id: "hallway_1", x: 0, y: 0, w: 3, h: 12 },
      { id: "hallway_2", x: 3, y: 0, w: 3, h: 2 },
    ],
  };

  const problems = checkLayout(layout, input);

  assert.ok(
    problems.some((p) => p.code === "HW2" && p.severity === "error"),
    "Expected HW2 error when hallway segments share less than 3 ft",
  );
});

it("accepts a connected hallway network even when the segments are not consecutive connections", () => {
  const layout = {
    rooms: [],
    hallway_segments: [
      { id: "hallway_1", x: 0, y: 0, w: 3, h: 12 },
      { id: "hallway_3", x: 3, y: 9, w: 3, h: 3 },
      { id: "hallway_2", x: 3, y: 0, w: 3, h: 9 },
    ],
  };

  const problems = checkLayout(layout, input);

  assert.ok(
    !problems.some((p) => p.code === "HW2"),
    "Expected no HW2 error because all segments belong to one connected network",
  );
});

it("accepts a living room touching the correct entrance edge", () => {
  const layout = {
    rooms: [
      { name: "living", type: "living", x: 0, y: 0, w: 12, h: 12 },
      { name: "kitchen", type: "kitchen", x: 12, y: 0, w: 8, h: 8 },
    ],
    hallway_segments: [],
  };

  const problems = checkLayout(layout, input);

  assert.ok(
    !problems.some((p) => p.code === "E1"),
    "Expected no E1 error because the living room touches the south/bottom edge",
  );
});

it("rejects a living room that does not touch the entrance edge", () => {
  const layout = {
    rooms: [
      { name: "living", type: "living", x: 5, y: 5, w: 12, h: 12 },
      { name: "kitchen", type: "kitchen", x: 17, y: 5, w: 8, h: 8 },
    ],
    hallway_segments: [],
  };

  const problems = checkLayout(layout, input);

  assert.ok(
    problems.some((p) => p.code === "E1" && p.severity === "error"),
    "Expected E1 error because the living room does not touch the south/bottom edge",
  );
});

it("uses north orientation when determining the entrance edge", () => {
  const rotatedInput = {
    ...input,
    entrance: "S",
    north: "down",
  };

  const layout = {
    rooms: [
      { name: "living", type: "living", x: 0, y: 28, w: 12, h: 12 },
      { name: "kitchen", type: "kitchen", x: 12, y: 28, w: 8, h: 8 },
    ],
    hallway_segments: [],
  };

  const problems = checkLayout(layout, rotatedInput);

  assert.ok(
    !problems.some((p) => p.code === "E1"),
    "Expected no E1 error because south maps to the top edge when north is down",
  );
});

describe("checker.js - H2 room size regression tests", () => {
  it("accepts a bathroom whose dimensions are valid after rotation", () => {
    const testInput = {
      ...input,
      rooms: [
        { name: "living", type: "living" },
        { name: "bathroom_1", type: "bathroom" },
      ],
    };

    const layout = {
      rooms: [
        { name: "living", type: "living", x: 0, y: 0, w: 12, h: 12 },
        { name: "bathroom_1", type: "bathroom", x: 12, y: 0, w: 7, h: 5 },
      ],
      hallway_segments: [],
    };

    const problems = checkLayout(layout, testInput);

    assert.ok(
      !problems.some((p) => p.code === "H2" && p.rooms.includes("bathroom_1")),
      "Expected 7x5 bathroom to pass because its sorted dimensions satisfy the 5x7 minimum",
    );
  });

  it("uses custom room minimum dimensions from input", () => {
    const testInput = {
      ...input,
      rooms: [
        { name: "living", type: "living" },
        {
          name: "bedroom_1",
          type: "bedroom",
          min: [8, 9],
        },
      ],
    };

    const layout = {
      rooms: [
        { name: "living", type: "living", x: 0, y: 0, w: 12, h: 12 },
        { name: "bedroom_1", type: "bedroom", x: 12, y: 0, w: 8, h: 9 },
      ],
      hallway_segments: [],
    };

    const problems = checkLayout(layout, testInput);

    assert.ok(
      !problems.some((p) => p.code === "H2" && p.rooms.includes("bedroom_1")),
      "Expected custom minimum dimensions [8, 9] to override the default bedroom minimum",
    );
  });

  it("rejects room dimensions below a custom minimum", () => {
    const testInput = {
      ...input,
      rooms: [
        { name: "living", type: "living" },
        {
          name: "bedroom_1",
          type: "bedroom",
          min: [8, 12],
        },
      ],
    };

    const layout = {
      rooms: [
        { name: "living", type: "living", x: 0, y: 0, w: 12, h: 12 },
        { name: "bedroom_1", type: "bedroom", x: 12, y: 0, w: 10, h: 10 },
      ],
      hallway_segments: [],
    };

    const problems = checkLayout(layout, testInput);

    assert.ok(
      problems.some((p) => p.code === "H2" && p.rooms.includes("bedroom_1")),
      "Expected H2 error because the bedroom does not meet the custom 8x12 minimum",
    );
  });

  it("rejects a room whose dimensions do not match its pinned width and height", () => {
    const testInput = {
      ...input,
      rooms: [
        { name: "living", type: "living" },
        { name: "bedroom_1", type: "bedroom" },
      ],
      pins: [{ room: "bedroom_1", width: 12, height: 12 }],
    };

    const layout = {
      rooms: [
        { name: "living", type: "living", x: 0, y: 0, w: 12, h: 12 },
        { name: "bedroom_1", type: "bedroom", x: 12, y: 0, w: 10, h: 12 },
      ],
      hallway_segments: [],
    };

    const problems = checkLayout(layout, testInput);

    assert.ok(
      problems.some((p) => p.code === "H2" && p.rooms.includes("bedroom_1")),
      "Expected H2 error because the bedroom does not match its pinned width",
    );
  });

  it("reports a pinned room that is missing from the layout", () => {
    const testInput = {
      ...input,
      rooms: [
        { name: "living", type: "living" },
        { name: "bedroom_1", type: "bedroom" },
      ],
      pins: [{ room: "bedroom_1", width: 12 }],
    };

    const layout = {
      rooms: [{ name: "living", type: "living", x: 0, y: 0, w: 12, h: 12 }],
      hallway_segments: [],
    };

    const problems = checkLayout(layout, testInput);

    assert.ok(
      problems.some((p) => p.code === "H2" && p.rooms.includes("bedroom_1")),
      "Expected H2 error because the pinned bedroom is missing",
    );
  });
});

describe("checker.js - F1/F5 reachability regression tests", () => {
  it("reports F5 when a room is disconnected from the entrance", () => {
    const testInput = {
      ...input,
      rooms: [
        { name: "living", type: "living" },
        { name: "bedroom_1", type: "bedroom" },
      ],
    };

    const layout = {
      rooms: [
        { name: "living", type: "living", x: 0, y: 0, w: 12, h: 12 },
        { name: "bedroom_1", type: "bedroom", x: 20, y: 0, w: 10, h: 10 },
      ],
      hallway_segments: [],
    };

    const problems = checkLayout(layout, testInput);

    assert.ok(
      problems.some((p) => p.code === "F5" && p.rooms.includes("bedroom_1")),
      "Expected F5 for a bedroom disconnected from the living room",
    );
  });

  it("reports F5 when a hallway is disconnected from the entrance", () => {
    const layout = {
      rooms: [{ name: "living", type: "living", x: 0, y: 0, w: 12, h: 12 }],
      hallway_segments: [{ id: "hallway_1", x: 20, y: 0, w: 3, h: 12 }],
    };

    const problems = checkLayout(layout, input);

    assert.ok(
      problems.some((p) => p.code === "F5" && p.rooms.includes("hallway_1")),
      "Expected F5 for a hallway disconnected from the entrance",
    );
  });

  it("accepts a room reachable through a hallway", () => {
    const testInput = {
      ...input,
      rooms: [
        { name: "living", type: "living" },
        { name: "bedroom_1", type: "bedroom" },
      ],
    };

    const layout = {
      rooms: [
        { name: "living", type: "living", x: 0, y: 0, w: 12, h: 12 },
        { name: "bedroom_1", type: "bedroom", x: 15, y: 0, w: 10, h: 10 },
      ],
      hallway_segments: [{ id: "hallway_1", x: 12, y: 0, w: 3, h: 12 }],
    };

    const problems = checkLayout(layout, testInput);

    assert.ok(
      !problems.some(
        (p) =>
          p.code === "F5" &&
          (p.rooms.includes("bedroom_1") || p.rooms.includes("hallway_1")),
      ),
      "Expected the bedroom and hallway to be reachable through the hallway",
    );
  });

  it("reports F1 when a bedroom can only be reached through another bedroom", () => {
    const testInput = {
      ...input,
      plot: [40, 40],
      rooms: [
        { name: "living", type: "living" },
        { name: "bedroom_1", type: "bedroom" },
        { name: "bedroom_2", type: "bedroom" },
      ],
    };

    const layout = {
      rooms: [
        { name: "living", type: "living", x: 0, y: 0, w: 12, h: 12 },
        { name: "bedroom_1", type: "bedroom", x: 12, y: 0, w: 10, h: 10 },
        { name: "bedroom_2", type: "bedroom", x: 22, y: 0, w: 10, h: 10 },
      ],
      hallway_segments: [],
    };

    const problems = checkLayout(layout, testInput);

    assert.ok(
      problems.some((p) => p.code === "F1" && p.rooms.includes("bedroom_2")),
      "Expected F1 because bedroom_2 is only reachable through bedroom_1",
    );
  });

  it("does not report F1 when a bedroom is independently accessible", () => {
    const testInput = {
      ...input,
      rooms: [
        { name: "living", type: "living" },
        { name: "bedroom_1", type: "bedroom" },
        { name: "bedroom_2", type: "bedroom" },
      ],
    };

    const layout = {
      rooms: [
        { name: "living", type: "living", x: 0, y: 0, w: 12, h: 12 },
        { name: "bedroom_1", type: "bedroom", x: 12, y: 0, w: 10, h: 10 },
        { name: "bedroom_2", type: "bedroom", x: 0, y: 12, w: 10, h: 10 },
      ],
      hallway_segments: [],
    };

    const problems = checkLayout(layout, testInput);

    assert.ok(
      !problems.some((p) => p.code === "F1"),
      "Expected no F1 because both bedrooms are independently accessible",
    );
  });

  it("uses the first requested room as the entrance when no living room exists", () => {
    const testInput = {
      ...input,
      rooms: [
        { name: "bedroom_1", type: "bedroom" },
        { name: "bedroom_2", type: "bedroom" },
      ],
    };

    const layout = {
      rooms: [
        { name: "bedroom_1", type: "bedroom", x: 0, y: 0, w: 10, h: 10 },
        { name: "bedroom_2", type: "bedroom", x: 20, y: 0, w: 10, h: 10 },
      ],
      hallway_segments: [],
    };

    const problems = checkLayout(layout, testInput);

    assert.ok(
      problems.some((p) => p.code === "F5" && p.rooms.includes("bedroom_2")),
      "Expected F5 because bedroom_2 is disconnected from the first requested room",
    );
  });

  it("reports a disconnected bedroom as F5, not F1", () => {
    const testInput = {
      ...input,
      rooms: [
        { name: "living", type: "living" },
        { name: "bedroom_1", type: "bedroom" },
      ],
    };

    const layout = {
      rooms: [
        { name: "living", type: "living", x: 0, y: 0, w: 12, h: 12 },
        { name: "bedroom_1", type: "bedroom", x: 20, y: 0, w: 10, h: 10 },
      ],
      hallway_segments: [],
    };

    const problems = checkLayout(layout, testInput);

    assert.ok(
      problems.some((p) => p.code === "F5" && p.rooms.includes("bedroom_1")),
      "Expected F5 for the disconnected bedroom",
    );

    assert.ok(
      !problems.some((p) => p.code === "F1" && p.rooms.includes("bedroom_1")),
      "A disconnected bedroom should not also receive F1",
    );
  });
});

it("rejects multiple short hallway segments whose lengths add up to 12 ft", () => {
  const layout = {
    rooms: [],
    hallway_segments: [
      { id: "hallway_1", x: 0, y: 0, w: 3, h: 6 },
      { id: "hallway_2", x: 3, y: 0, w: 3, h: 6 },
    ],
  };

  const problems = checkLayout(layout, input);

  assert.ok(
    problems.some((p) => p.code === "HW1" && p.severity === "error"),
    "Expected HW1 because neither hallway segment is 12 ft long",
  );
});

it("rejects overlapping hallway segments", () => {
  const layout = {
    rooms: [],
    hallway_segments: [
      { id: "hallway_1", x: 0, y: 0, w: 3, h: 12 },
      { id: "hallway_2", x: 2, y: 4, w: 3, h: 12 },
    ],
  };

  const problems = checkLayout(layout, input);

  assert.ok(
    problems.some(
      (p) =>
        p.code === "H3" &&
        p.rooms.includes("hallway_1") &&
        p.rooms.includes("hallway_2"),
    ),
    "Expected H3 for overlapping hallway segments",
  );
});
