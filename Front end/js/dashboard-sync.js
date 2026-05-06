// Dashboard Synchronization Module
// Enables real-time synchronization between multiple dashboard instances
// Uses BroadcastChannel API for cross-tab communication

(function() {
    'use strict';
    
    // Create BroadcastChannel for synchronization
    const syncChannel = new BroadcastChannel('andorra-dashboard-sync');
    
    // State to track if we're currently updating from a sync (to prevent loops)
    let isSyncing = false;
    
    // Initialize synchronization
    window.DashboardSync = {
        // Send a sync event to other dashboard instances
        broadcast: function(eventType, data) {
            if (isSyncing) return; // Don't broadcast if we're currently syncing
            
            syncChannel.postMessage({
                type: eventType,
                data: data,
                timestamp: Date.now(),
                source: window.location.pathname
            });
            
            console.log('📡 Broadcast:', eventType, data);
        },
        
        // Listen for sync events from other dashboard instances
        on: function(eventType, callback) {
            syncChannel.addEventListener('message', function(event) {
                const message = event.data;
                
                // Ignore messages from the same window
                if (message.source === window.location.pathname) {
                    return;
                }
                
                if (message.type === eventType) {
                    isSyncing = true;
                    try {
                        callback(message.data);
                    } finally {
                        // Reset sync flag after a short delay to allow UI updates
                        setTimeout(function() {
                            isSyncing = false;
                        }, 100);
                    }
                }
            });
        },
        
        // Check if we're currently syncing (to prevent update loops)
        isSyncing: function() {
            return isSyncing;
        },
        
        // Initialize sync listeners for common events
        init: function() {
            console.log('✅ Dashboard synchronization initialized');
            
            // Listen for scenario changes
            this.on('scenario_change', function(data) {
                console.log('🔄 Syncing scenario:', data.scenario);
                const slider = document.getElementById('scenario-slider');
                if (slider && slider.value != data.scenario) {
                    slider.value = data.scenario;
                    slider.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });
            
            // Listen for year changes
            this.on('year_change', function(data) {
                console.log('🔄 Syncing year:', data.year);
                const slider = document.getElementById('time-slider');
                if (slider && slider.value != data.year) {
                    slider.value = data.year;
                    document.getElementById('year-display').textContent = data.year;
                    slider.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });
            
            // Listen for tab changes
            this.on('tab_change', function(data) {
                console.log('🔄 Syncing tab:', data.tab);
                const buttons = document.querySelectorAll('.tab-button');
                buttons.forEach(function(btn) {
                    if (btn.dataset.tab === data.tab) {
                        btn.classList.add('active');
                        btn.dispatchEvent(new Event('click', { bubbles: true }));
                    } else {
                        btn.classList.remove('active');
                    }
                });
            });
        }
    };
    
    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            window.DashboardSync.init();
        });
    } else {
        window.DashboardSync.init();
    }
})();
