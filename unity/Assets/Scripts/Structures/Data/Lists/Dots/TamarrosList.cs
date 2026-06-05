using UnityEngine;
using System;
using System.Xml;

[CreateAssetMenu(fileName = "Tamarros", menuName = "Scriptable/Data/Tamarros")]
[Serializable]
public class TamarrosList : DataList{
    public override void LoadData() {
        XmlTools tools = GetXmlTools();
        data.Clear();

        foreach (XmlElement element in tools.nodeList) {
            Data newData = new();

            newData.coord = GetCoordsByNodeStrings(element.Attributes["lat"].Value, element.Attributes["lon"].Value);
            if (newData.coord == Vector3.zero) continue;

            data.Add(newData);
        }
    }
}

