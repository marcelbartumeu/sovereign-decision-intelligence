using System;
using UnityEngine;
using WebSocketSharp;
using WebSocketSharp.Server;

public class ServerCommandsHandler : WebSocketBehavior {

    protected override void OnMessage(MessageEventArgs e) {

        string message = e.Data;
        Debug.Log("Received: " + message);

        try {
            UnityMainThreadDispatcher dispatcher = UnityMainThreadDispatcher.Instance;
            if (dispatcher == null) {
                Debug.LogWarning("Dispatcher not ready");
                return;
            }
            dispatcher.Enqueue(() => {
                Debug.Log($"Server received background message: {message}");

                if (VideoManager.instance == null) {
                    Debug.LogWarning("VideoManager instance is null!");
                    return;
                }

                switch (message) {
                    case "PAUSE":
                        VideoManager.instance.Pause();
                        break;
                    case "RESET":
                        VideoManager.instance.Reset();
                        break;
                    case "NEXT":
                        VideoManager.instance.NextStep();
                        break;
                    case "PREVIOUS":
                        VideoManager.instance.PreviousStep();
                        break;
                }
            });
        } catch (Exception ex) {
            Debug.LogError($"OnMessage error: {ex}");
        }
    }

}
