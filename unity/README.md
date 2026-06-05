# cdm-server-maqueta

## 📋 Project Overview
Interactive 3D visualization application showcasing geographic and touristic data of Andorra (rivers, mountains, bike trails, etc.) built with Unity.
Includes a server component for tablet-based remote control **cdm-client-maqueta**.

## 🚀 Getting Started
**Prerequisites** <br/>
* **Unity Version**: 2022.3.36f1 <br/>
* **Target Platform**: Windows
* **Dependencies:** Uses [NuGetForUnity](https://github.com/GlitchEnzo/NuGetForUnity) to manage [WebSocketSharp.Standard 1.0.3](https://www.nuget.org/packages/WebSocketSharp.Standard/).

## 🏗️ Project Structure
   |-📁 Scripts <br/>
   |---📁 Editor (Custom editor in order to add/update easily the data segments)<br/>
   |---📁 Managers (Singletons that manage their respective field) <br/>
   |---📁 Server (Scripts with all the server logic) <br/>
   |---📁 Structures <br/>
   |------📁 Data (Defines `Data`, `Step` and `CoordinatesRefs` structures) <br/>
   |---------📄 Data (Define the structure of the data with injectable fields (Sprite, Color etc)) <br/>
   |---------📄 DataList (Abstract class to load all the necessary information for the current data segment) <br/>
   |---------📁 Lists (Scripts that inherit from DataList. Separated with `Dots` and `Tracks` data) <br/>
   |-📁 Resources (Has all the .xml files for the data, .xml for tranlations and sprites to show during the projection on the text part) <br/>
   |-📁 Scriptables (Has all the scriptables objects created such as `Data` and `Steps` definitions) <br/>

## 🗺️ Data Visualization Setup
The video structure can be found at the *Video Manager* game object.

### Adding Visualization Segments
**Add its data**
1. Create a *Data* Scriptable Object, several options will appear
2. Choose one if the structure matches. If not, create a new custom script (scriptable object) in Scripts/Structures/Data/Lists
3. DataList is subscribed to CoordManager.OnLoadData so it will load the data automatically

**Add to the video**
1. Create a *Steps* Scriptable Object
2. In Unity Editor, select the Video Manager GameObject
3. Click the "+" button on the first Steps array to add a new segment 
4. Attach the created Scriptable Object at the desired position
5. Locate the second Steps array, the attached scriptable will be reflected displaying the fields to modify
6. Use the data scriptable object seen before to feed this segment

## ⚙️ Server Configuration
Adjust these settings in the **Server** component inspector:
* **IP**: The fixed IP address of the server machine is currently `127.0.0.1` <br/>
* **Port**: The server is currently listening to port `8080` <br/>

## 📢 Available Commands
The server listens to the following string commands:
* `PAUSE` - Toggle pause/play on the video
* `NEXT` / `PREVIOUS` - Navigate through data segments
* `RESET` - Return to the beginning
