using System;
using System.Xml;
using UnityEngine;

[CreateAssetMenu(fileName = "Todos", menuName = "Scriptable/Data/Todos")]
[Serializable]
public class Imprescindibles : DataList {

    public string placeId;
    public bool isAll;

    public override void LoadData() {
        XmlTools tools = GetXmlTools();
        data.Clear();

        foreach (XmlElement element in tools.nodeList) {

            if (element.GetAttribute("id").ToString() != placeId && !isAll)
                continue;

            Data newData = new();

            // Coord
            XmlElement coordElement = element["coord"];
            if (coordElement == null) continue;
            string[] split = coordElement.InnerText.Split(";");
            newData.coord = GetCoordsByNodeStrings(split[0], split[1]);
            if (newData.coord == Vector3.zero) continue;

            // Name
            XmlElement nameElement = element["name"];
            if (nameElement != null)
                newData.AddField(Types.Name, nameElement.InnerText);

            // Parrish
            XmlElement parElement = element["par"];
            if (parElement != null)
                newData.AddField(Types.Parrish, parElement.InnerText);

            data.Add(newData);
        }
    }
}
