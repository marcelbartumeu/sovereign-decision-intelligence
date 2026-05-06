using System.Xml;
using UnityEngine;

[CreateAssetMenu(fileName = "Simple", menuName = "Scriptable/Data/Simple")]
public class SimpleList : DataList {

    public override void LoadData() {
        XmlDocument document = CoordManager.instance.OpenXmlDoc(asset);

        if (document == null) return;

        data.Clear();
        XmlNodeList dataNodes_wa = document.SelectNodes("/Main/imp");

        foreach (XmlElement element in dataNodes_wa) {

            Data newData = new();

            XmlElement coordElement = element["coord"];
            if (coordElement == null) continue;
            string[] split = coordElement.InnerText.Split(";");
            newData.coord = GetCoordsByNodeStrings(split[0], split[1]);
            if (newData.coord == Vector3.zero) continue;

            data.Add(newData);
        }
    }
}
