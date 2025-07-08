import remynd
import asyncio
import uuid
import time
import json
import os
import configparser
from datetime import datetime
from html import escape

# Create a MessageCenter instance
extension_path = os.path.dirname(os.path.realpath(__file__))
loop = asyncio.get_event_loop()
message_center = remynd.MessageCenter(loop)
kvstore = remynd.Dictionary(message_center.extension_id)

# https://docs.python.org/3/library/configparser.html
config = configparser.ConfigParser({
    'AutoSummary': True,
    'CaptureReminder': True,
    'TrackDataAmount': True
})
config_path = os.path.join(extension_path, 'config.ini')
config.read(config_path)
if 'Settings' not in config:
    config['Settings'] = {}
settings = config['Settings']

def get_time():
    return time.time()

def get_timestamp():
    return int(get_time())

def date_str(ts, with_seconds=False):
    if with_seconds:
        return datetime.fromtimestamp(ts).strftime("%d/%m/%y, %H:%M:%S")
    return datetime.fromtimestamp(ts).strftime("%d/%m/%y, %H:%M")

async def register():
    # print("Extension ID:", extension_id)

    reg_msg = {
        "event": "extension.register",
        "data": {
            "capabilities": {
                "standalone": [
                    {
                        "title": "UI Playground",
                        "event": "uiPlayground",
                    },
                ],
                "settings": [
                    {
                        "title": "Settings",
                        "event": "settings",
                    },
                ],
                "call": [
                    {
                        "title": "Create Summary",
                        "event": "callSummary",
                    }
                ],
                "frame": [
                    {
                        "title": "Window List",
                        "event": "windowList",
                    }
                ],
            }
        }
    }

    reg_resp = await message_center.send_message(reg_msg)
    print("Registration:", json.dumps(reg_resp, indent=4))

async def showWindow(result=''):
    html = f"""
    <html><body style="background-color: #1f1f1f; color: white; font-family: 'SF Pro'">
    <h2>UI Playground</h2>
    <h3>ASK</h3>
    <form id="form1">
    <label for="query" style="margin: 0.5em;">Query:</label>
    <br>
    <textarea name="query" style="width: 90%; height: 10%; margin: 0.5em; font-family: courier; font-size: 0.85em;">What did I do last week?</textarea>
    <br>
    <button type="submit" style="margin: 0.5em; padding: 1em;">ASK »</button>
    </form>
    <h3>SEARCH</h3>
    <form id="form2">
    <label for="query" style="margin: 0.5em;">Query:</label>
    <br>
    <textarea name="query" style="width: 90%; height: 10%; margin: 0.5em; font-family: courier; font-size: 0.85em;">hello</textarea>
    <br>
    <button type="submit" style="margin: 0.5em; padding: 1em;">SEARCH »</button>
    </form>
    <h3>VIEW</h3>
    <form id="form3">
    <label for="db" style="margin: 0.5em;">Call records:</label>
    <div id="calls" style="margin: 0.5em; font-family: courier; font-size: 0.85em;"></div>
    <br>
    <button id="prev" type="button" style="margin: 0.5em; padding: 1em;">« Prev 10</button>
    <button id="filtered" type="button" style="padding: 1em;">Filtered View</button>
    <button type="submit" style="padding: 1em;">VIEW</button>
    <button id="next" type="button" style="margin: 0.5em; padding: 1em;">Next 10 »</button>
    </form>
    </body></html>
    """

    # https://developer.mozilla.org/en-US/docs/Web/API/FormDataEvent
    script = """
    form1 = document.getElementById("form1");
    form1.addEventListener("submit", event => {
        event.preventDefault();
        var json = Object.fromEntries(new FormData(form1));
        json.id = form1.getAttribute("id");
        window.webkit.messageHandlers.remynd.postMessage(json);
    });
    form2 = document.getElementById("form2");
    form2.addEventListener("submit", event => {
        event.preventDefault();
        var json = Object.fromEntries(new FormData(form2));
        json.id = form2.getAttribute("id");
        window.webkit.messageHandlers.remynd.postMessage(json);
    });
    form3 = document.getElementById("form3");
    form3.addEventListener("submit", event => {
        event.preventDefault();
        var json = Object.fromEntries(new FormData(form3));
        json.id = form3.getAttribute("id");
        window.webkit.messageHandlers.remynd.postMessage(json);
    });
    """
    view_msg = {
        "event": "ui.renderHTML",
        "data": {
            "html": html,
            "userScript": script,
            "width": 900,
            "height": 500,
            "reopen": True
        }
    }

    window_id = await kvstore.get_int('window_id')
    if window_id:
        view_msg['data']['windowID'] = window_id

    remynd.log("Sending view render request")
    view_resp = await message_center.send_message(view_msg)

    window_id = view_resp['windowID']
    remynd.log("HTML rendered in window: ", window_id)
    await kvstore.set_int('window_id', window_id)

    # small timeout needed to let DOM load properly
    time.sleep(0.5)
    await loadCalls(get_timestamp())

async def loadCalls(before, after=0):
    window_id = await kvstore.get_int('window_id')

    if not window_id:
        print("window not found")
        return
    
    if after:
        sql = f"SELECT id, title, participants, endDate FROM Call WHERE id > {after} ORDER BY id ASC LIMIT 10;"
    else:
        sql = f"SELECT id, title, participants, endDate FROM Call WHERE id < {before} ORDER BY id DESC LIMIT 10;"
    
    msg = {
        "event": "sql.runSQL",
        "data": {
            "sql": sql,
            "db": "extras"
        }
    }
    remynd.log("Sending sql request...")
    response = await message_center.send_message(msg)
    result = response.get('result')

    if not result:
        return False
    
    if after:
        result = list(reversed(result))
    
    first_ts = result[0]['id'] if result else get_timestamp()
    last_ts = result[-1]['id'] if result else 0
    
    items = []
    filter = []

    for idx, c in enumerate(result):
        items.append(f"""
            <input type="radio" id="call{c['id']}" name="calls" value="{c['id']}"{' ' if idx else ' checked'} />
            <label for="call{c['id']}">{date_str(c['id'])} <b>{c['title'] or 'n/a'}</b></label>
            """)
        filter.append({'startDate': c['id'], 'endDate': int(c.get('endDate') or get_timestamp())})
    
    items = '<br>\n   '.join(items)
    filter = list(reversed(filter))
    
    script = f"""
    (function() {{
        function updateContent(e) {{
            const resultElem = document.getElementById("calls");
            resultElem.innerHTML = `{items}`;
            document.getElementById("prev").onclick = function(e) {{
                window.webkit.messageHandlers.remynd.postMessage({{id: 'form3', prev: {last_ts}}})
            }}
            document.getElementById("next").onclick = function(e) {{
                window.webkit.messageHandlers.remynd.postMessage({{id: 'form3', next: {first_ts}}})
            }}
            document.getElementById("filtered").onclick = function(e) {{
                window.webkit.messageHandlers.remynd.postMessage({{id: 'form3', filter: JSON.parse(`{json.dumps(filter)}`)}})
            }}
        }}

        if (document.readyState === "complete") {{
            updateContent(null);
        }} else {{
            document.addEventListener("DOMContentLoaded", updateContent);
        }}
    }})()
    """

    view_msg = {
        "event": "ui.renderHTML",
        "data": {
            "windowID": window_id,
            "userScript": script
        }
    }

    remynd.log("Sending js script request")
    view_resp = await message_center.send_message(view_msg)

    if view_resp.get('windowID') == window_id:
        remynd.log("JS executed succefully in window: ", window_id)
        return True
    
    remynd.log("Failed to execute js in window: ", window_id, view_resp)
    return False

async def showSettings():
    html = f"""
    <html><body style="background-color: #1f1f1f; color: white; font-family: 'SF Pro'">
    <h2>Settings</h2>
    <form id="settings">
    <h3>SUMMARY</h3>
    <label for="summary" style="margin: 0.5em;">Auto Summary:</label>
    <input type="checkbox" id="summary" name="summary"{' checked' if settings.getboolean('AutoSummary') else ''} />
    <br>
    <h3>CAPTURE</h3>
    <label for="reminder" style="margin: 0.5em;">Capture Reminder:</label>
    <input type="checkbox" id="reminder" name="reminder"{' checked' if settings.getboolean('CaptureReminder') else ''} />
    <br>
    <label for="track" style="margin: 0.5em;">Track Data Amount:</label>
    <input type="checkbox" id="track" name="track"{' checked' if settings.getboolean('TrackDataAmount') else ''} />
    <br>
    <br>
    <button id="close" type="button" style="padding: 1em;">Close</button>
    <button type="submit" style="margin-left: 1em; padding: 1em;">SAVE</button>
    </form>
    </body></html>
    """

    # https://developer.mozilla.org/en-US/docs/Web/API/FormDataEvent
    script = """
    form = document.getElementById("settings");
    form.addEventListener("submit", event => {
        event.preventDefault();
        var json = Object.fromEntries(new FormData(form));
        json.id = form.getAttribute("id");
        window.webkit.messageHandlers.remynd.postMessage(json);
    });
    document.getElementById("close").onclick = function(e) {
        window.webkit.messageHandlers.remynd.postMessage({ id: 'settings', 'close': true });
    };
    """
    view_msg = {
        "event": "ui.renderHTML",
        "data": {
            "html": html,
            "userScript": script,
            "width": 900,
            "height": 500,
            "reopen": True
        }
    }

    window_id = await kvstore.get_int('settings_window_id')
    if window_id:
        view_msg['data']['windowID'] = window_id

    remynd.log("Sending view render request")
    view_resp = await message_center.send_message(view_msg)

    window_id = view_resp['windowID']
    remynd.log("HTML rendered in window: ", window_id)
    await kvstore.set_int('settings_window_id', window_id)

async def callSummary(call):
    call_id = call['id']
    remynd.log('Summarize call: ', json.dumps(call, indent=4))
    script_msg = {
        "event": "layerScript.run",
        "data": {
            "scriptID": "0FFC00D4-4535-405F-9C6F-B10936E595EE",
            "scriptInput": str(call_id)
        }
    }
    remynd.log("Sending summary request")
    summary_msg = await message_center.send_message(script_msg)
    remynd.log("Got summary result")
    summary_dict = json.loads(summary_msg['summary'])
    # kvstore.set(f'summary:{call_id}', summary_msg['summary'])

    remynd.log("Render HTML window...")

    participants = ", ".join(summary_dict['participants'])
    summary = summary_dict['summary']
    html = f"""
        <html>
        <body style="background-color: #1f1f1f; color: #f0f0f0; font-family: 'SF Pro'; margin: 16px;">
        <h1>Call Summary</h1>
        <h3>Participants</h3>
        {participants}
        <h3>Summary</h3>
        {escape(summary)}
        <br>
        <br>
        <button id="share" type="button" style="padding: 1em;">Share</button>
        <p id="log"></p>
        </body>
        </html>
    """

    script = f"""
        const shareData = {{
            title: "Summary",
            text: `{escape(summary)}`
        }};

        document.getElementById("share").onclick = function (ev) {{
            navigator
                .share(shareData)
                .then(() =>
                    document.getElementById("log").textContent = 'MDN shared successfully'
                )
                .catch((e) =>
                    document.getElementById("log").textContent = 'Error: ' + e
                );
        }};
    """

    view_msg = {
        "event": "ui.renderHTML",
        "data": {
            "html": html,
            "userScript": script,
            "width": 400,
            "height": 600
        }
    }

    window_id = await kvstore.get_int('window_id')
    if window_id:
        view_msg['data']['windowID'] = window_id

    remynd.log("Sending view render request")
    view_resp = await message_center.send_message(view_msg)
    window_id = view_resp['windowID']
    remynd.log("Summary rendered in window: ", window_id)

    await kvstore.set_int('window_id', window_id)

async def windowList(msg):
    ts = msg['timestamp']
    pos = msg['position']

    remynd.log("Show window list at: ", ts)
    img_msg = {
        "event": "recorder.getFrame",
        "data": {
            "position": pos
        }
    }
    remynd.log("Sending getFrame request")
    msg = await message_center.send_message(img_msg)
    imageData = msg.get('imageData')

    sql_msg = {
        "event": "sql.runSQL",
        "data": {
            "sql": f"""
                select ApplicationWindow.id, name, localizedName, bundleIdentifier from ApplicationWindow 
                join ApplicationRun on ApplicationWindow.applicationRunId = ApplicationRun.id
                join Application on ApplicationRun.applicationId = Application.id
                where firstSeenAt <= DATETIME({ts}, 'auto') and lastSeenAt >= DATETIME({ts}, 'auto')
            """
        }
    }
    remynd.log("Sending runSQL request")
    msg = await message_center.send_message(sql_msg)

    print(msg)

    wnd_list = '\n'.join(map(lambda w: f"""
        <li>{escape(w['localizedName']) + ' (' + escape(w['bundleIdentifier']) + ')' + '<br>' + escape(w['name'] or 'n/a')}</li>
    """, msg['result']))

    html = """
        <html>
        <body style="background-color: #1f1f1f; color: #f0f0f0; font-family: 'SF Pro'; margin: 16px;">
        <img id="image" style="max-width: 100%;" />
        <h1>Window List</h1>
        <ol id="list">
        </ol>
        </body>
        </html>
    """

    script = f"""
    (function() {{
        document.getElementById("image").setAttribute("src", "data:image/png;charset=utf-8;base64,{imageData}");
        document.getElementById("list").innerHTML = `{wnd_list}`;
    }}())
    """

    view_msg = {
        "event": "ui.renderHTML",
        "data": {
            "title": date_str(ts, with_seconds=True),
            "userScript": script,
            "width": 900,
            "height": 600,
            "reopen": True
        }
    }

    window_id = await kvstore.get_int('list_window_id')
    if window_id:
        view_msg['data']['windowID'] = window_id
    else:
        view_msg['data']['html'] = html

    remynd.log("Sending view render request")
    view_resp = await message_center.send_message(view_msg)
    window_id = view_resp['windowID']
    remynd.log("List rendered in window: ", window_id)

    await kvstore.set_int('list_window_id', window_id)

async def handleJSCallback(msg):
    print('Execute:', msg)
    form_id = msg.get('id')

    if not form_id:
        return
    
    if form_id == 'settings':
        window_id = await kvstore.get_int('settings_window_id')

        # Close settings window
        if msg.get('close'):
            if not window_id:
                return
            
            msg = {
                "event": "ui.closeWindow",
                "data": {
                    "windowID": window_id
                }
            }

            remynd.log("Sending closeWindow request...")
            response = await message_center.send_message(msg)
            print("Response: ", response)
            await kvstore.remove('settings_window_id')
            return

        # Save settings
        settings['AutoSummary'] = msg.get('summary', 'off')
        settings['CaptureReminder'] = msg.get('reminder', 'off')
        settings['TrackDataAmount'] = msg.get('track', 'off')

        with open(config_path, 'w') as cf:
            config.write(cf)

        if not window_id:
            return
        
        script = """
        (function() {
        const doneEl = document.createElement("span");
        doneEl.innerHTML = "&nbsp;✅";
        document.getElementById("settings").appendChild(doneEl);
        setTimeout(function () {
            doneEl.remove();
        }, 1000);
        })()
        """
        # hljs.highlightBlock(document.getElementById("result"));
        view_msg = {
            "event": "ui.renderHTML",
            "data": {
                "windowID": window_id,
                "userScript": script
            }
        }

        remynd.log("Sending js script request")
        response = await message_center.send_message(view_msg)
        print("Response: ", response)

        return

    if form_id == 'form1':
        msg = {
            "event": "ui.openAsk",
            "data": {
                "text": msg.get('query')
            }
        }

        remynd.log("Sending ask request...")
        response = await message_center.send_message(msg)
        print("Response: ", response)
        return

    if form_id == 'form2':
        msg = {
            "event": "ui.openSearch",
            "data": {
                "text": msg.get('query'),
                "startDate": get_timestamp() - 30 * 24 * 60 * 60,
                "endDate": get_timestamp() - 30 * 60,
                "transcripts": True,
                "apps": ["Mail", "Safari"],
                "sort": "time"
            }
        }

        remynd.log("Sending search request...")
        response = await message_center.send_message(msg)
        print("Response: ", response)
        return

    if form_id == 'form3':
        prev = msg.get('prev')

        if prev:
            await loadCalls(prev)
            return

        next = msg.get('next')

        if next:
            await loadCalls(0, after=next)
            return

        filt = msg.get('filter')

        msg = {
            "event": "ui.openView",
            "data": {
                "date": int(msg.get('calls', get_timestamp() - 10)) + 1,
                # "zoomLevel": "month",
            }
        }

        if filt:
            msg['data']['filter'] = {
                'ranges': filt,
                'description': f"Calls { date_str(filt[0]['startDate'])} - {date_str(filt[-1]['endDate'])}"
            }

        remynd.log("Sending view request...")
        response = await message_center.send_message(msg)
        print("Response: ", response)
        return

# async def check_recording_task(timeout, minutes):
#     while True:
#         await asyncio.sleep(timeout)

#         last_frame_ts = await kvstore.get_int('last_frame_ts')

#         if not last_frame_ts: continue

#         if get_timestamp() - last_frame_ts > minutes * 60:
#             msg = {
#                 "event": "ui.showNotification",
#                 "data": {
#                     "text": "Recording paused\nclick here to resume."
#                 }
#             }
#             response = await message_center.send_message(msg)
#             print("Notification id: ", response)

# async def handleDidCaptureFrame(msg):
#     print('Frame captured!', msg)
#     await kvstore.set_int('last_frame_ts', int(msg['timestamp']))
#     frame_count = await kvstore.increment('frame_count')
#     print('Frame count:', frame_count)

#     if frame_count == 1:
#         await kvstore.set_int('first_frame_ts', int(msg['timestamp']))

# Handler for incoming events on the 'ui' channel
async def ui_handler(channel, event, msg):
    print(f"{event}:\n", json.dumps(msg, indent=4))

    if event == 'positionDidChange':
        print(msg)
        if await kvstore.get_int('list_window_id'):
            await windowList(msg)
#     elif event == 'notificationCallback':
#         await handleNotificationCallback(msg)

# Handler for incoming events on the 'message' channel
async def msg_handler(channel, event, msg):
    print(f"{event}:\n", json.dumps(msg, indent=4))

    if event == 'uiPlayground':
        await showWindow()
    elif event == 'settings':
        await showSettings()
    elif event == 'jsEventFired':
        await handleJSCallback(msg)
    elif event == 'windowWillClose':
        if msg['windowID'] == await kvstore.get_int('window_id'):
            await kvstore.remove('window_id')
        elif msg['windowID'] == await kvstore.get_int('settings_window_id'):
            await kvstore.remove('settings_window_id')
        elif msg['windowID'] == await kvstore.get_int('list_window_id'):
            await kvstore.remove('list_window_id')
    elif event == 'callSummary':
        call = msg.get('call')
        if call:
            await callSummary(call)
    elif event == 'windowList':
        await windowList(msg)

# Handler for incoming events on the 'recorder' channel
async def recorder_handler(channel, event, msg):
    print(f"{event}:\n", json.dumps(msg, indent=4))
    # if event == 'didCaptureFrame':
    #     await handleDidCaptureFrame(msg)

# Handler for incoming events on the 'system' channel
async def sys_handler(channel, event, msg):
    print(f"{event}:\n", json.dumps(msg, indent=4))

# Handler for incoming events on the 'call' channel
async def call_handler(channel, event, msg):
    print(f"{event}:\n", json.dumps(msg, indent=4))

# loop.create_task(showWindow())
loop.create_task(register())
# loop.create_task(check_recording_task(1, 0))
message_center.subscribe('ui', ui_handler)
message_center.subscribe('messages', msg_handler)
message_center.subscribe('system', sys_handler)
message_center.subscribe('calls', call_handler)
message_center.subscribe('recorder', recorder_handler)

remynd.log("Waiting for extension triggers...")
message_center.run() # Will run forever
