using System.Globalization;
using System.Xml;
using UnityEngine;
using System;

[CreateAssetMenu(fileName = "Ciclo", menuName = "Scriptable/Data/Ciclo")]
[Serializable]
public class CicloturismeList : DataTrailList{
    public override void LoadData() {

        XmlTools tools = GetXmlTools();
        data.Clear();

        bool isFirst = true;

        foreach (XmlNode element in tools.nodeList) {
            Data newData = new();

            newData.coord = GetCoordsByNodeStrings(element.Attributes["lat"].Value, element.Attributes["lon"].Value);
            if (newData.coord == Vector3.zero) continue;

            if (isFirst) {
                lastAdded = newData.coord;
                isFirst = false;
            }

            if (DistanceChecker(newData.coord))
                data.Add(newData);

        }
    }

}
