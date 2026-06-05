using System.Collections.Generic;
using System.Xml;
using UnityEngine;

public class LanguageManager : MonoBehaviour {

    #region VARIABLES
    public static LanguageManager instance;

    private Dictionary<string, string> engDictionary = new();
    private Dictionary<string, string> catDictionary = new();

    [SerializeField]
    private TextAsset catLanguage;
    [SerializeField]
    private TextAsset engLanguage;

    private void Awake() {
        if (instance == null)
            instance = this;
    }
    #endregion

    #region EVENTS
    void Start() {
        LoadDictionaries(catLanguage);
        LoadDictionaries(engLanguage);
    }
    #endregion

    #region METHDOS
    /// <summary>
    /// Load Dictionaries by reading the XML document
    /// </summary>
    private void LoadDictionaries(TextAsset asset) {
        // Get the xml doc
        XmlDocument document = LoadXmlDocument(asset);

        // If fail, return
        if (document == null)
            return;

        // Get the node (=sectcion) for the warning messages
        XmlNodeList massageNodes = document.SelectNodes("/Main/message");

        // Iterates the warning section
        foreach (XmlElement node in massageNodes) {
            // Get the key for the current element (=line)
            string key = node.GetAttribute("key");

            if (!string.IsNullOrEmpty(key)) {
                switch (asset.name) {
                    case "Eng":
                        engDictionary.Add(key, node.InnerText);
                        break;
                    case "Cat":
                        catDictionary.Add(key, node.InnerText);
                        break;
                }
            }
            else {
                Debug.Log("Empty key encountered in <b>warnings</b>");
            }
        }
    }

    /// <summary>
    /// Open and load the XML Document and returns it
    /// </summary>
    /// <returns></returns>
    private XmlDocument LoadXmlDocument(TextAsset asset) {
        // If fail, return
        if (asset == null) {
            Debug.Log("Unable to open <b>Language XML</b>");
            return null;
        }

        // Create a xmlDoc
        XmlDocument xmlDocument = new();

        try {
            // Load the xml content
            xmlDocument.LoadXml(asset.text);
        }
        catch (XmlException e) {
            Debug.Log("Error Loading the XML: " + e);
            return null;
        }

        return xmlDocument;
    }

    /// <summary>
    /// Returns the message asigned to the given key
    /// </summary>
    /// <param name="key"></param>
    /// <returns></returns>
    public string GetTextByKey(string key, string language) {

        // Get the section
        string message = "";

        switch (language) {
            case "Cat":
                // Try to get the value from its respective dictionary with the given key
                if (!catDictionary.TryGetValue(key, out message)) {
                    Debug.Log("Unable to get message from <b>Cat</b> with key <b>" + key + "</b>");
                }
                break;
            case "Eng":
                if (!engDictionary.TryGetValue(key, out message)) {
                    Debug.Log("Unable to get message from <b>Eng</b> with key <b>" + key + "</b>");
                }
                break;
        }
        return message;
    }
    #endregion
}