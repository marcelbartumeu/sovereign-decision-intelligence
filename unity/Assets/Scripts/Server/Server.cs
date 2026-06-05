using System;
using UnityEngine;
using WebSocketSharp.Server;

public class Server : MonoBehaviour {

    [Header("Server Settings")]
    [SerializeField] private int serverPort = 8080;

    private WebSocketServer wssv;

    void Start() {
        wssv = new WebSocketServer(serverPort);

        wssv.AddWebSocketService<ServerCommandsHandler>("/");

        wssv.Start();
        Debug.Log("WebSocket Server started on ws://localhost:8080");
    }


    void OnDestroy() {
        try {
            wssv?.Stop();
        }
        catch (Exception e) {
            Debug.LogError($"Server stop error: {e}");
        }
    }

}

