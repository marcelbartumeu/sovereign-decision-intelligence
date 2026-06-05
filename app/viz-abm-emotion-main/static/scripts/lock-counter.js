export class LockCounter {
    constructor(id) {
        this.id = id;
        this.lockCount = 0;   // How many active locks?
        this.lockPromise = Promise.resolve(); // Holds the wait promise
        this.lockResolver = null; // Function to resolve the lock promise
    }
  
    // Called when another agent interacts with this one
    lock() {
        navigator.locks.request('lock-counter-' + this.id, async (lock) => {
            this.lockCount++;
  
            if (this.lockCount === 1) {
                // First interaction -> Create a lock promise
                this.lockPromise = new Promise((resolve) => {
                    this.lockResolver = resolve;
                });
            }
        });
    }
  
    // Called when an interaction with this agent ends
    unlock() {
        navigator.locks.request('lock-counter-' + this.id, async (lock) => {
            if (this.lockCount > 0) {
                this.lockCount--;
            
                if (this.lockCount === 0 && this.lockResolver) {
                    this.lockResolver(); // Allow movement
                    this.lockResolver = null;
                }
            }
        });
    }

    async accessLock(){
        return this.lockPromise
    }
}