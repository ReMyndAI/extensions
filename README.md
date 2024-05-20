# Layer1 Extensions Guide

## Prerequisites

### Python
The Layer1 app bundle includes the Python 3.11 runtime for running extension code. The Python standard library and some basic modules are included in this installation, but any extra modules required by an extension should be included inside its folder.

### Redis
All communication between extensions and Layer1 happens via Redis channels. The Redis server is packaged with Layer1 and is launched at app startup. Extensions do not need to worry about the details of this communication, and should use the `MessageCenter` APIs in the `layer1` module to communicate with the app.

### Layer1
A module named `layer1` is required for extensions to communicate with the parent app. The library is fully self-contained in the `layer1.py` file: this file should be packaged with your extension.

## First steps
You can use the `demo/` directory as a template for your extension folder.

1. Create a new folder for your extension and copy `layer1.py` to it. The name of this folder does not matter.

2. Create a `manifest.json` file with the following keys:
```JSON
{
    "name": "My Extension Name",
    "description": "Enter a detailed description of your extension here.",
    "version": "1.0.0"
}
```

3. Create a `main.py` file. Use the `layer1.MessageCenter` class to subscribe to app events and send messages to Layer1. Here's an example:
```Python
import layer1
import asyncio
import uuid

# Create a run loop and MessageCenter instance
loop = asyncio.get_event_loop()
message_center = layer1.MessageCenter(loop)

# Handler for incoming events on the 'recorder' channel
async def recorder_handler(channel, event, msg):
    if event == 'didCaptureFrame':
        print("Frame captured!")

# Subscribe to all incoming events on the 'recorder' channel
message_center.subscribe('recorder', recorder_handler)
layer1.log("Waiting for incoming events...")
message_center.run() # Will run forever
```

You can also use `layer1.Dictionary` to store non-critical data in Redis. For a more complex example see `demo/main.py`.

4. You can run and debug your extension directly from an editor such as VS Code while the Layer1 app is running. It is not required for Layer1 to launch your extension process for debugging purposes.

## Events (Notifications)

Below is a list of channels used to broadcast app-wide events. An extension may subscribe to as many channels as needed.

### `system` channel

* `applicationDidLaunch` An application did launch
<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "pid": 28676,
    "executableURL": "file:///System/Applications/Mail.app/Contents/MacOS/Mail",
    "launchDate": 724704879.7656999,
    "appName": "Mail",
    "isActive": true,
    "bundleURL": "file:///System/Applications/Mail.app/",
    "timestamp": 724704880.046299,
    "bundleID": "com.apple.mail"
}
```
</details>

* `applicationDidActivate` An application was activated
<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "pid": 28676,
    "executableURL": "file:///System/Applications/Mail.app/Contents/MacOS/Mail",
    "launchDate": 724704879.7656999,
    "appName": "Mail",
    "isActive": true,
    "bundleURL": "file:///System/Applications/Mail.app/",
    "timestamp": 724704879.960106,
    "bundleID": "com.apple.mail"
}
```
</details>

* `applicationDidDeactivate` An application was deactivated
<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "pid": 28676,
    "executableURL": "file:///System/Applications/Mail.app/Contents/MacOS/Mail",
    "launchDate": 724704879.7656999,
    "appName": "Mail",
    "isActive": false,
    "bundleURL": "file:///System/Applications/Mail.app/",
    "timestamp": 724704895.917056,
    "bundleID": "com.apple.mail"
}
```
</details>

* `applicationDidTerminate` An application was terminated
<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "pid": 745,
    "executableURL": "file:///System/Applications/Mail.app/Contents/MacOS/Mail",
    "isActive": false,
    "launchDate": 724626816.0797701,
    "appName": "Mail",
    "bundleURL": "file:///System/Applications/Mail.app/",
    "timestamp": 724704877.431679,
    "bundleID": "com.apple.mail"
}
```
</details>

### `recorder` channel

* `didCaptureFrame` Layer1 recorder captured a new frame
<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    // Integer position for better precision
    "position": 1021807592431, 
    // Floating value timestamp
    // timestamp = position / 600
    "timestamp": 1703012654.0516667
}
```
</details>

### `calls` channel

* `callDidStart` Layer1 detected a new call (Zoom, etc.)
<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "id": 1703024824,
    "appName": "Zoom",
    "participants": [
        "John Galt",
        "Jonathan Livingston"
    ],
    "callID": 1703024824,
    "startDate": 1703024824.354
}
```
</details>

* `callDidEnd` Layer1 detected a call end
<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "endDate": 1703024835.4429998,
    "appName": "Zoom",
    "startDate": 1703024824.354,
    "id": 1703024824,
    "meetingId": 7961251252,
    "participants": [
        "John Galt",
        "Steve Jobs",
        "Steve Ballmer",
    ],
    "title": "John Galt's Personal Meeting Room",
    "callID": 1703024824
}
```
</details>

* `callRecordingStarted` Call audio recording started
<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "appName": "Zoom",
    "participants": [
        "John Galt"
    ],
    "callID": 1703024824,
    "startDate": 1703024824.354,
    "id": 1703024824
}
```
</details>

* `callRecordingStopped` Call audio recording stopped
<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "endDate": 1703024835.4429998,
    "appName": "Zoom",
    "startDate": 1703024824.354,
    "id": 1703024824,
    "meetingId": 7961251252,
    "participants": [
        "John Galt",
        "Steve Jobs",
        "Steve Ballmer",
    ],
    "title": "John Galt's Personal Meeting Room",
    "callID": 1703024824
}
```
</details>

### `ui` channel

* `positionDidChange` Notifies about the current frame position in Viewer
<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    // Integer position for better precision
    "position": 1021807592431, 
    // Floating value timestamp
    // timestamp = position / 600
    "timestamp": 1703012654.0516667
}
```
</details>

## Messages channel

The `messages` channel is used for one-to-one (app-to-extension or extension-to-app) messages. Each message contains an `event` field which contains the function name, and optional `data`.

In order to send a message to the `messages` channel use the `message_center.send_message()` function. In case you provide user-triggered functions or expect other messages from the app to your extension, subscribe to the `messages` channel via `message_center.subscribe()` method.

### `messages` events

* `jsEventFired` Notifies about some JSON data posted from JavaScript which is running within an HTML window created by the extension.
<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    // Any data passed from within JS using `layer1` message handler
    // For example:
    // window.webkit.messageHandlers.layer1.postMessage({ id: 'settings', close: true });
    "id": "settings",
    "close": true
}
```
</details>

* `notificationCallback` Notifies when the user clicks a popup shown using `showNotification` function with some action data specified
<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    "action": {
        // This could be any string data specified in showNotification function
        "data": "[724724275, 724724276, 724724277, 724724278]"
    },
    "notificationID": "05707C81-9C2F-43AF-B595-8926BEEC94EC"
}
```
</details>

* `goBack` Notifies that 'Back' button was pressed
<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "windowID": 1234,
    // Optional
    "windowTag": "main"
}
```
</details>

* `nextItem` Notifies that 'Next' button was pressed
<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "windowID": 1234,
    // Optional
    "windowTag": "main"
}
```
</details>

* `previousItem` Notifies that 'Previous' button was pressed
<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "windowID": 1234,
    // Optional
    "windowTag": "main"
}
```
</details>

* `windowWillClose` Notifies that one of the extension's windows is about to close
<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "windowID": 1234,
    // Optional
    "windowTag": "main"
}
```
</details>

### `extension` functions

* `extension.register` Registers an extension's capabilities. Send this message if you want to create standalone UI, settings UI or some entity functions.
<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    "event": "extension.register",
    "data": {
        "capabilities": {
            // Optional – standalone UI windows
            // in this example the 'uiPlayground' function should open some playground window
            "standalone": [
                {
                    "title": "UI Playground", // Menu title
                    "event": "uiPlayground",  // Event name to use (posted within 'messages' channel)
                },
            ],
            // Optional – settings windows
            // in this example the 'settings' function should open settings window
            "settings": [
                {
                    "title": "Settings",
                    "event": "settings",
                },
            ],
            // Optional – functions that process recorded calls
            // in this example the 'callSummary' function will receive a `call` entity
            "call": [
                {
                    "title": "Create Summary",
                    "event": "callSummary",
                }
            ],
            // Optional – functions that process current position
            // in this example the 'windowList' function will receive a player position
            // (as timestamp and more precise integer value)
            "frame": [
                {
                    "title": "List Windows",
                    "event": "windowList",
                }
            ],
        }
    }
}
```
Response:
```JSON
"OK"
```
</details>

### `system` functions

* `system.getLocale` Get a list of user preferred locales (language and region codes). Use this function to determine correct language and format.

<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "event": "system.getLocale"
}
```
Response:
```JavaScript
[
    'en_US', 'de_DE', 'ru_RU'
]
```
</details>

* `system.getRunningApps` Get a list of currently running applications. 

<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "event": "system.getRunningApps"
}
```
Response:
```JavaScript
{
    "runningApps": [
        {
            "executableURL": "file:///System/Library/CoreServices/loginwindow.app/Contents/MacOS/loginwindow",
            "isActive": false,
            "pid": 597,
            "bundleURL": "file:///System/Library/CoreServices/loginwindow.app/",
            "appName": "loginwindow",
            "bundleID": "com.apple.loginwindow"
        },
        {
            "appName": "CoreLocationAgent",
            "executableURL": "file:///System/Library/CoreServices/CoreLocationAgent.app/Contents/MacOS/CoreLocationAgent",
            "pid": 1151,
            "bundleURL": "file:///System/Library/CoreServices/CoreLocationAgent.app/",
            "bundleID": "com.apple.CoreLocationAgent",
            "isActive": false
        },
        {
            "appName": "Mail",
            "executableURL": "file:///System/Applications/Mail.app/Contents/MacOS/Mail",
            "isActive": false,
            "pid": 1764,
            "bundleURL": "file:///System/Applications/Mail.app/",
            "bundleID": "com.apple.mail",
            "launchDate": 1702343607.162433
        },
        {
            "bundleURL": "file:///System/Volumes/Preboot/Cryptexes/App/System/Applications/Safari.app/",
            "bundleID": "com.apple.Safari",
            "pid": 1765,
            "appName": "Safari",
            "launchDate": 1702343607.17921,
            "executableURL": "file:///System/Volumes/Preboot/Cryptexes/App/System/Applications/Safari.app/Contents/MacOS/Safari",
            "isActive": false
        },
        //
        // ...
        //
        {
            "launchDate": 1702389912.3138142,
            "bundleURL": "file:///Applications/Xcode.app/",
            "executableURL": "file:///Applications/Xcode.app/Contents/MacOS/Xcode",
            "bundleID": "com.apple.dt.Xcode",
            "pid": 7793,
            "isActive": false,
            "appName": "Xcode"
        }
    ]
}
```
</details>

### `recorder` functions

* `recorder.getFrame` Get a specified frame in PNG format (base64 encoded).
<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    "event": "recorder.getFrame",
    "data": {
        // Either position or timestamp must be specified
        // timestamp = position / 600

        // Optional
        // more precise Integer position of a frame
        "position": 1021493241857,
        // Optional
        // less precise floating point timestamp of a frame
        "timestamp": 1702488736.4283333
    }
}
```
Response:
```JSON
{
    "imageData": "<base64-encoded-png-image-data>"
}
```
</details>

* `recorder.startCallRecording` Start an audio recording of a specified app.

<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "event": "recorder.startCallRecording",
    "data": {
        "pid": 1234
    }
}
```
Response:
```JSON
"OK"
```
</details>

* `recorder.stopCallRecording` Stop an audio recording of a specified app.

<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "event": "recorder.stopCallRecording",
    "data": {
        "pid": 1234
    }
}
```
Response:
```JSON
"OK"
```
</details>

### `ui` functions

* `ui.renderHTML` Render some HTML (and JavaScript) within a separate window.

<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    "event": "ui.renderHTML",
    "data": {
        // Optional - window title
        "title": "Window Title",
        // Optional - HTML
        "html": "<html><body><h1>Hello world!</h1><div id=\"content\"></div></body></html>",
        // Optional - JavaScript
        "userScript": "document.getElementById(\"content\").textContent = \"Lorem ipsum\";",
        // Optional - window ID if it's already displayed
        "windowID": 1234,
        // Optional - window width (for new window)
        "width": 900,
        // Optional - window height (for new window)
        "height": 600,
        // Optional – reopen window if specified windowID not found
        "reopen": true,
        // Optional – place window on top of other app windows (could be overriden by user)
        "alwaysOnTop": false,
        // Optional - window tag (string)
        "windowTag": "main",
        // Optional - display a 'back' button in the window toolbar and set its enabled state.
        // When pressed the extension will receive a message called 'goBack'
        "backEnabled": true,
        // Optional - display a 'previous' button in the window toolbar and set its enabled state
        // When pressed the extension will receive a message called 'previousItem'
        "prevEnabled": true,
        // Optional - display a 'next' button in the window toolbar and set its enabled state
        // When pressed the extension will receive a message called 'nextItem'
        "nextEnabled": true,
    }
}
```
Response:
```JSON
{
    "windowID": 1234
}
```
</details>

* `ui.closeWindow` Close a previously displayed window.

<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "event": "ui.closeWindow",
    "data": {
        "windowID": 1234
    }
}
```
Response:
```JSON
"OK"
```
</details>

* `ui.showNotification` Show a small popup notification with optional tap action.

<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    "event": "ui.showNotification",
    "data": {
        "text": "Call summary ready.\nClick here to view",
        // Optional
        "action": {
            // Any string data that will be passed
            // to the action handler
            // (see ui.notificationCallback event)
            "data": "This a call summary."
        }
    }
}
```
Response:
```JSON
{
    "notificationID": "a82ae604-9537-49a5-b0bb-25b07cf8c746"
}
```
</details>

* `ui.openAsk` Open Ask (GPT) chat window.

<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    "event": "ui.openAsk",
    "data": {
        // Optional - query to send
        "text": "what did i do yesterday?"
    }
}
```
Response:
```JSON
"OK"
```
</details>

* `ui.openSearch` Open Search window.

<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    "event": "ui.openAsk",
    "data": {
        // Optional - query string
        "text": "amazon",
        // Optional - filter by app name
        "apps": [
            "Safari",
            "Mail"
        ],
        // Optional - start timestamp
        "startDate": 1699574400,
        // Optional - end timestamp
        "endDate": 1699833600,
        // Optional - search in transcriptions
        "transcripts": true,
        // Optional - sorting option relevance/time
        "sort": "time"
    }
}
```
Response:
```JSON
"OK"
```
</details>

* `ui.openView` Open Viewer.

<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    "event": "ui.openView",
    "data": {
        // Optional - player position timestamp
        "date": 1699833600,
        // Optional - zoom level day/week/month/year
        "zoomLevel": "month",
        // Optional - filter frames to selected time ranges
        "filter": [
            {
                "startDate": 1699574400,
                "endDate": 1699833600
            },
            {
                "startDate": 1701388800,
                "endDate": 1702166400
            }
        ]   
    }
}
```
Response:
```JSON
"OK"
```
</details>

* `ui.viewPosition` Set Viewer position (when it's on screen).

<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    "event": "ui.viewPosition",
    "data": {
        // Optional – Integer position for better precision
        "position": 1021807592431, 
        // Optional – Floating value timestamp
        // timestamp = position / 600
        "timestamp": 1703012654.0516667
        // Optional - frame selection strategy (closest/leading/trailing)
        "frame": "leading",
    }
}
```
Response:
```JSON
"OK"
```
</details>

### `sql` functions

* `sql.runSQL` Run arbitrary SQL statement on the main Layer1 SQLite database (read-only).

<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    "event": "sql.runSQL",
    "data": {
        "sql": "SELECT id, title, startDate, endDate FROM Call ORDER BY id DESC;",
        // Optional – database to run the query (main/extras)
        "db": "extras"
    }
}
```
Response:
```JavaScript
// NOTE: there's a limit of 100 records per response.
// If you need more records make your own pagination
[
    {
        "id": 1702402242,
        "startDate": 1702402242.804,
        "endDate": 1702404087.014,
        "title": "John Galt's Personal Meeting Room"
    },
    {
        "startDate": 1702315884.984,
        "title": "John Galt's Personal Meeting Room",
        "endDate": 1702318045.139,
        "id": 1702315884
    },
    //
    // ...
    //
    {
        "startDate": 1701279838.45,
        "title": "Jonathan's Personal Meeting Room",
        "endDate": 1701282196.374,
        "id": 1701279838
    }
]
 ```
</details>

### `ax` functions

* `ax.getProcessTree` Get specified process tree of UI elements.
<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "event": "ax.getProcessTree",
    "data": {
        "pid": 1234
    }
}
```
Response:
```JSON
{
    "windows": [
        {
            "bounds": [
                [ 88, 454 ],
                [ 1556, 436 ]
            ],
            "uuid": "6EA3D3D6-4503-4FD4-B10F-CC56F1177374",
            "title": "vz1500",
            "subrole": "AXStandardWindow",
            "id": "FinderWindow",
            "children": [
                {
                    "uuid": "36CCEE2B-7913-4527-91A9-5CAECBA4A300",
                    "role": "AXStaticText",
                    "bounds": [
                        [ 320, 454 ],
                        [ 503, 52 ]
                    ],
                    "children": []
                },
                {
                    "role": "AXButton",
                    "children": [],
                    "subrole": "AXMinimizeButton",
                    "bounds": [
                        [ 127, 472 ],
                        [ 14, 16 ]
                    ],
                    "uuid": "D57B34B0-48D9-4F5B-AB1D-1EB271075A5A"
                },
                {
                    "subrole": "AXFullScreenButton",
                    "bounds": [
                        [ 147, 472 ],
                        [ 14, 16 ]
                    ],
                    "role": "AXButton",
                    "uuid": "7EB74A1A-69DF-4D43-8817-0A9AAD0D1B4E",
                    "children": [ "..." ]
                },
                {
                    "uuid": "00A9ED87-D1F3-444B-AA84-62B056A4F926",
                    "subrole": "AXCloseButton",
                    "bounds": [
                        [ 107, 472 ],
                        [ 14, 16 ]
                    ],
                    "role": "AXButton",
                    "children": []
                },
                {
                    "uuid": "B6DD0342-06BD-44FF-9440-B3899F186D87",
                    "title": "tab bar",
                    "description": "Tab bar, 3 tabs",
                    "bounds": [
                        [ 235, 506 ],
                        [ 1409, 28 ]
                    ],
                    "role": "AXTabGroup",
                    "children": [ "..." ]
                },
                {
                    "role": "AXSplitGroup",
                    "uuid": "C4751B4A-A5FE-4D0D-A836-F20E78326A95",
                    "children": [
                        {
                            "role": "AXSplitGroup",
                            "bounds": [
                                [ 236, 454 ],
                                [ 1408, 436 ]
                            ],
                            "children": [ "..." ],
                            "uuid": "F1B73762-E455-4FAF-B3CF-DCFD7F745A67"
                        },
                        {
                            "role": "AXSplitter",
                            "uuid": "0172A876-5995-4E56-9C56-513688B8A5F6",
                            "bounds": [
                                [ 235, 534 ],
                                [ 1, 356 ]
                            ],
                            "children": []
                        },
                        {
                            "uuid": "7A454EEA-23E7-4C55-9F32-618893F2AAF5",
                            "bounds": [
                                [ 88, 506 ],
                                [ 147, 384 ]
                            ],
                            "children": [ "..." ],
                            "id": "_NS:61",
                            "role": "AXScrollArea"
                        }
                    ],
                    "bounds": [
                        [ 88, 454 ],
                        [ 1556, 436 ]
                    ]
                }
            ],
            "role": "AXWindow"
        },
        {
            "uuid": "A25C00E7-7CCA-4CC8-92B8-A12293F43274",
            "role": "AXScrollArea",
            "bounds": [
                [ 0, 0 ],
                [ 1728, 1117 ]
            ],
            "description": "desktop",
            "children": [ "..." ]
        }
    ],
    "pid": 1778
}
```
</details>

* `ax.getNodeTree` Get specified node tree of UI elements.
<details>
<summary><b>Example</b> (click to expand)</summary>

```JSON
{
    "event": "ax.getNodeTree",
    "data": {
        "uuid": "A25C00E7-7CCA-4CC8-92B8-A12293F43274"
    }
}
```
Response:
```JSON
{
    "node": {
        "description": "desktop",
        "uuid": "A25C00E7-7CCA-4CC8-92B8-A12293F43274",
        "role": "AXScrollArea",
        "bounds": [
            [ 0, 0 ], [ 1728, 1117 ]
        ],
        "children": [
            {
                "children": [
                    {
                        "bounds": [
                            [ 1631, 606 ],
                            [ 64, 64 ]
                        ],
                        "description": "Old Firefox Data",
                        "children": [],
                        "url": "file:///Users/username/Desktop/Old%20Firefox%20Data/",
                        "role": "AXImage",
                        "title": "Old Firefox Data",
                        "uuid": "2D413F98-4E6C-4C70-A217-BC6D968708FB"
                    },
                    {
                        "role": "AXImage",
                        "description": "Screenshots",
                        "uuid": "BE36E9C2-797F-4DA6-A62C-66593B4BFEB3",
                        "bounds": [
                            [ 1631, 494 ],
                            [ 64, 64 ]
                        ],
                        "children": [],
                        "title": "Screenshots"
                    },
                    {
                        "title": "twitter_web.py",
                        "bounds": [
                            [ 1631, 382 ],
                            [ 64, 64 ]
                        ],
                        "children": [],
                        "role": "AXImage",
                        "description": "twitter_web.py",
                        "url": "file:///Users/username/Desktop/twitter_web.py",
                        "uuid": "FA8E341C-58D2-4CF1-9A66-66E5F90C189B"
                    },
                    {
                        "title": "Movies",
                        "children": [],
                        "role": "AXImage",
                        "uuid": "2BEB0BFB-3793-42E7-8FED-3140602EFF30",
                        "description": "Movies",
                        "bounds": [
                            [ 1631, 270 ],
                            [ 64, 64 ]
                        ]
                    },
                    {
                        "url": "file:///Users/username/Desktop/feed_stat.pdf",
                        "children": [],
                        "title": "feed_stat.pdf",
                        "bounds": [
                            [ 1631, 158 ],
                            [ 64, 64 ]
                        ],
                        "uuid": "F16AB573-FDAE-445D-91A3-F199B3EC44C9",
                        "description": "feed_stat.pdf",
                        "role": "AXImage"
                    },
                    {
                        "title": "Images",
                        "uuid": "D98C15AD-C1FA-42F8-B5A5-8AC820E034B3",
                        "description": "Images",
                        "bounds": [
                            [ 1631, 46 ],
                            [ 64, 64 ]
                        ],
                        "role": "AXImage",
                        "children": []
                    }
                ],
                "description": "desktop",
                "uuid": "B57EE98F-4F5E-4944-B30E-B379E1951532",
                "role": "AXGroup",
                "bounds": [
                    [ 0, 0 ],
                    [ 1728, 1117 ]
                ]
            }
        ]
    }
}
```
</details>

* `ax.setAttributeValue` Set an Accessibility attribue.
<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    "event": "ax.setAttributeValue",
    "data": {
        "pid": 1778,
        "attribute": "title",
        // Optional – set boolean value
        "boolValue": true,
        // Optional – set integer value
        "intValue": 123,
        // Optional – set string value
        "stringValue": "Hello"
    }
}
```
Response:
```JSON
"OK"
```
</details>

### `edb` functions

* `edb.runEdgeQL` Run an artibtrary EdgeQL query on the main Layer1 EdgeDB database.
<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    "event": "edb.runEdgeQL",
    "data": {
        "query": "...",
        // Optional
        "variables": [
            "x": 123,
            "y": 456
        ]
    }
}
```
Response:
```JSON
"OK"
```
</details>

### `layerScript` functions

* `layerScript.run` Set custom title of a call entity.
<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    "event": "layerScript.run",
    "data": {
        "scriptID": "0FFC00D4-4535-405F-9C6F-B10936E595EE",
        "scriptInput": "1701279838"
    }
}
```
Response:
```JSON
{
    "summary": "'[\n    {\n        \"start\": \"2023-10-02 16:32:01.713\",\n        \"end\": \"2023-10-02 16:34:11.651\",\n        \"title\": \"User Engagement and Feedback on New Release\",\n        \"summary\": \"The team discusses the user engagement metrics following the new version release, noting an increase in downloads and app usage. They observe that users are opening the app multiple times, indicating active use. The early feedback is considered significant, showing that the update has improved functionality.\"\n    },\n    {\n        \"start\": \"2023-10-02 16:34:20.714\",\n        \"end\": \"2023-10-02 16:37:28.994\",\n        \"title\": \"Technical Issues and Fixes\",\n        \"summary\": \"The team identifies a problem with the Auto Start feature not working as intended. They discuss the need to update the API to a newer version to ensure the app appears in the correct section of system settings for auto-starting. A fix has been submitted, and a new build is awaited to confirm the resolution. Action items include checking the preference settings for auto start and considering an explicit setting for this feature.\"\n    },\n    {\n        \"start\": \"2023-10-02 16:38:34.907\",\n        \"end\": \"2023-10-02 16:43:49.118\",\n        \"title\": \"Feature Enhancements and User Interaction\",\n        \"summary\": \"The team discusses potential enhancements, including tracking the usage of a floating button and adding a pop-up notification for paused activities. They consider drawing attention to the floating button to increase its use. Additionally, there\'s mention of updating the onboarding process with a placeholder for search results. Action items include tracking the floating button\'s usage and implementing the discussed enhancements.\"\n    }\n]'"
}
```
</details>

### `calls` functions

* `calls.setTitle` Set custom title of a call entity.
<details>
<summary><b>Example</b> (click to expand)</summary>

```JavaScript
{
    "event": "calls.setTitle",
    "data": {
        "callID": 1701279838,
        "title": "Big Band Meeting"
    }
}
```
Response:
```JSON
"OK"
```
</details>

## TODO

 - Tips & Tricks
   - JS log
   - Setting up a LayerScript
   - Embedding HTML images
   - Call audio URLs