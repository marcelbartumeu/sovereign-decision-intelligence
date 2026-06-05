using System.Collections.Generic;
using System.Xml;
using UnityEngine;

[CreateAssetMenu(fileName = "Estripagecs", menuName = "Scriptable/Data/Estripagecs")]
public class EstripagecsList : DataList {
    public List<string> picId;

    public override void LoadData() {

        XmlTools tools = GetXmlTools();
        data.Clear();

        foreach (XmlElement element in tools.nodeList) {
            XmlNode elementNode = element.SelectSingleNode(".//ogr:PICS_ID", tools.nsmgr);
            if (elementNode == null) continue;

            if (!picId.Contains(elementNode.InnerText))
                continue;

            Data newData = new();

            // Coord
            newData.coord = GetGmlCoords(element, tools.nsmgr);
            if (newData.coord == Vector3.zero) continue;

            data.Add(newData);
        }
    }
}
