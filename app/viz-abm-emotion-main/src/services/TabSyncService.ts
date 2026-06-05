type SimulationMessage = {
  type:
    | 'PLAY' | 'PAUSE' | 'STEP_UPDATE' | 'SIMULATION_LOADED'
    | 'TIMER_OWNERSHIP' | 'REQUEST_TIMER_OWNERSHIP' | 'OWNERSHIP_RESPONSE'
    | 'FOLLOWED_AGENT_UPDATE' | 'MAP_STYLE_UPDATE' | 'FILTER_UPDATE'
    | 'SCENARIO_CHANGE' | 'YEAR_CHANGE' | 'MAP_LAYER_CHANGE';
  data?: {
    currentStep?: number;
    currentInterpolationStep?: number;
    simulationData?: any;
    timestamp?: number;
    tabId?: string;
    hasOwner?: boolean;
    followedAgent?: {
      agentId: string;
      agentType: string;
      emotion: string;
      transport: string;
    };
    useRealisticMap?: boolean;
    selectedAgentType?: string | null;
    selectedEmotionFilter?: string | null;
    // Scenario / year / map-layer sync
    scenario?: string;
    year?: number;
    mapLayer?: string;
  };
};

class TabSyncService {
  private channel: BroadcastChannel;
  private listeners: Set<(message: SimulationMessage) => void>;
  private tabId: string;
  private isTimerOwner: boolean;
  private lastMessageTimestamp: number;
  private ownershipTimeout: number | null;

  constructor() {
    this.channel = new BroadcastChannel('simulation-sync');
    this.listeners = new Set();
    this.tabId = Math.random().toString(36).substring(2, 9);
    this.isTimerOwner = false;
    this.lastMessageTimestamp = 0;
    this.ownershipTimeout = null;

    this.channel.onmessage = (event) => {
      const message = event.data as SimulationMessage;
      
      switch (message.type) {
        case 'REQUEST_TIMER_OWNERSHIP':
          if (this.isTimerOwner) {
            this.broadcast({
              type: 'OWNERSHIP_RESPONSE',
              data: { 
                hasOwner: true,
                tabId: this.tabId,
                timestamp: Date.now()
              }
            });
          }
          break;
        
        case 'OWNERSHIP_RESPONSE':
          if (message.data?.hasOwner) {
            this.isTimerOwner = false;
            if (this.ownershipTimeout) {
              clearTimeout(this.ownershipTimeout);
              this.ownershipTimeout = null;
            }
          }
          break;

        case 'FOLLOWED_AGENT_UPDATE':
          // Always deliver — never dropped by timestamp filter
          this.listeners.forEach(listener => listener(message));
          break;

        default:
          if (message.data?.timestamp && message.data.timestamp > this.lastMessageTimestamp) {
            this.lastMessageTimestamp = message.data.timestamp;
            this.listeners.forEach(listener => listener(message));
          }
          break;
      }
    };

    // Initialize timer ownership request
    this.initializeOwnership();
  }

  private initializeOwnership() {
    // Broadcast request for existing owner
    this.broadcast({
      type: 'REQUEST_TIMER_OWNERSHIP',
      data: { tabId: this.tabId }
    });

    // Wait briefly for response, if none received become owner
    this.ownershipTimeout = window.setTimeout(() => {
      if (!this.isTimerOwner) {
        console.log('No owner found, taking ownership');
        this.isTimerOwner = true;
      }
    }, 500) as unknown as number;
  }

  subscribe(callback: (message: SimulationMessage) => void) {
    this.listeners.add(callback);
    return () => {
      this.listeners.delete(callback);
    };
  }

  broadcast(message: SimulationMessage) {
    const messageWithTimestamp = {
      ...message,
      data: {
        ...message.data,
        timestamp: Date.now()
      }
    };
    this.channel.postMessage(messageWithTimestamp);
  }

  requestTimerOwnership() {
    this.initializeOwnership();
  }

  isOwner(): boolean {
    return this.isTimerOwner;
  }

  cleanup() {
    if (this.ownershipTimeout) {
      clearTimeout(this.ownershipTimeout);
    }
    this.channel.close();
  }
}

export const tabSyncService = new TabSyncService(); 