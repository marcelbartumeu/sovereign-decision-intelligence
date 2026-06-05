// --------------- EDITABLE CONFIGURATIONS ---------------
const SPEED_FACTOR = 0.75; // Slow factor [0, 1]
export const SHOW_H3_HEXAGONS = false;
export const FILTER_CONVERSATIONS_BY_AGENT_TYPE = true;

// ---------------- DEFAULT CONFIGURATIONS ----------------
export const DEFAULT_STOPPED_TRANSPORT_NAME = 'stopped';
export const DEFAULT_STOPPED_TRANSPORT_COLOR = 'black';
export const DEFAULT_STOPPED_TRANSPORT_INTERACTIVE = true;
export const SECONDS_PER_MINUTE = 3;
export const ANIMATION_MOVEMENT_SPEED = 25; // 1 FRAME PER 25ms OF SIMULATION (for measuring walk jumps based on route time)
export const SIMULATION_SPEED = Math.ceil(ANIMATION_MOVEMENT_SPEED / SPEED_FACTOR); // Slow factor of the simulation