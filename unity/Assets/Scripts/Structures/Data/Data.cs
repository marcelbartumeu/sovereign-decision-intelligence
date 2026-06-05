using System;
using System.Collections.Generic;
using UnityEngine;

public enum Types {Sprite, Place, Parrish, Name, Altitud, Guarded, Color, Size}

[Serializable]
public class Data {
    public Vector3 coord;
    public Dictionary<Types, object> fields = new();

    public void AddField(Types key, object value){
        if (!fields.TryAdd(key, value)) {
            Debug.LogWarning($"Duplicate field '{key}' detected for this data point. Keeping original value.");
        }
    }
    public bool GetField<T>(Types key, out T result) {

        if (fields.TryGetValue(key, out object value)) {
            if (value is T castedValue) {
                result = castedValue;
                return true;
            }
            Debug.LogWarning($"Type mismatch for {key}. Stored: {value.GetType()}, Requested: {typeof(T)}");
        }
        result = default;
        return false;
    }
}

