using System;
using System.Xml;
using UnityEngine;


[CreateAssetMenu(fileName = "Tamarro", menuName = "Scriptable/Data/Tamarro")]
[Serializable]
public class TamarroList : DataList {
    [Space]
    public Sprite sprite;
    public string par;

    public override void LoadData() {

        XmlTools tools = GetXmlTools();
        data.Clear();

        foreach (XmlElement element in tools.nodeList) {

            XmlElement parElement = element["par"];
            if (parElement == null || par != parElement.InnerText)
                continue;

            Data newData = new();

            // Coord
            newData.coord = GetCoordsByNodeStrings(element.Attributes["lat"].Value, element.Attributes["lon"].Value);
            if (newData.coord == Vector3.zero) continue;

            // Parrish Name            
            newData.AddField(Types.Parrish, parElement.InnerText);

            // Color
            XmlElement colorElement = element["color"];
            if (colorElement != null) {
                if (ColorUtility.TryParseHtmlString("#" + colorElement.InnerText, out Color color))
                    newData.AddField(Types.Color, color);
            }

            // Sprite
            newData.AddField(Types.Sprite, sprite);

            data.Add(newData);
        }
    }
}