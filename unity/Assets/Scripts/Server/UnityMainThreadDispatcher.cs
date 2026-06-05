using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class UnityMainThreadDispatcher : MonoBehaviour {
    public static UnityMainThreadDispatcher Instance;
    private readonly Queue<Action> executionQueue = new();
    private readonly List<Action> toExecute = new();

    private void Awake() {
        if (Instance == null) Instance = this;
    }

    public void Enqueue(Action action) {
        lock (executionQueue) {
            executionQueue.Enqueue(action);
        }
    }

    void Update() {
        lock (executionQueue) {
            while (executionQueue.Count > 0) {
                toExecute.Add(executionQueue.Dequeue());
            }
        }
        foreach (Action action in toExecute)
            action.Invoke();
        toExecute.Clear();
    }
}
