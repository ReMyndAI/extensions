import layer1
import asyncio
import json
import time
import os
import sys
from datetime import datetime, timezone
from base64 import b64encode

from jinja2 import Environment, PackageLoader, select_autoescape
env = Environment(
    loader=PackageLoader("main"),
    autoescape=select_autoescape()
)

# Create a MessageCenter instance
loop = asyncio.get_event_loop()
message_center = layer1.MessageCenter(loop)
kvstore = layer1.Dictionary(message_center.extension_id)

def get_time():
    return time.time()

def get_timestamp():
    return int(get_time())

def date_str(ts):
    return datetime.fromtimestamp(ts).strftime("%x")

def time_str(ts):
    return datetime.fromtimestamp(ts).strftime("%X")

async def register():
    layer1.log("Extension ID:", message_center.extension_id)

    reg_msg = {
        "event": "extension.register",
        "data": {
            "capabilities": {
                "call": [
                    {
                        "title": "Call Details",
                        "event": "callCopilot",
                    },
                    {
                        "title": "Create Summary",
                        "event": "callSummary",
                    }
                ],
            }
        }
    }

    reg_resp = await message_center.send_message(reg_msg)
    layer1.log("Registration:", json.dumps(reg_resp, indent=4))

    await kvstore.remove('entity')
    await kvstore.remove('window_id')

async def set_locale():
    import locale

    try:
        # set locale from env variables
        layer1.log("Set locale:", locale.setlocale(locale.LC_ALL, ''))
        return
    except:
        pass

    # set locale from system wide preferred languages
    msg = {
        "event": "system.getLocale"
    }
    lang_codes = await message_center.send_message(msg)

    for lc in lang_codes:
        lc = f"{lc}.UTF-8"

        try:
            # set locale from env variables
            layer1.log("Set locale:", locale.setlocale(locale.LC_ALL, lc))
            return
        except:
            pass

    layer1.log("WARNING: Unable to set locale!")

def encode_image(path):
    with open(os.path.dirname(__file__) + '/' + path, "rb") as f:
        return b64encode(f.read()).decode('ascii')
    
env.globals['encodeImage'] = encode_image
env.globals['getTimestamp'] = get_timestamp
env.globals['dateStr'] = date_str
env.globals['timeStr'] = time_str
env.globals['dumps'] = json.dumps

async def getTranscription(call_id):
    transcription = []
    count = 1
    last_id = -1

    while True:
        msg = {
            "event": "sql.runSQL",
            "data": {
                "sql": f"select * from TranscriptionSegment where callID = {call_id} and id > {last_id} order by id",
                "db": "extras"
            }
        }
        layer1.log(f"Sending sql request for transcription {count}...")
        response = await message_center.send_message(msg)
        result = response.get('result')
        count += 1

        if not result:
            break;
    
        transcription += result
        last_id = result[-1]['id']
        
    return transcription

async def checkTranscription(call_id):
    msg = {
        "event": "sql.runSQL",
        "data": {
            "sql": f"select * from TranscriptionSegment where callID = {call_id} limit 1",
            "db": "extras"
        }
    }
    layer1.log(f"Sending sql request for transcription...")
    response = await message_center.send_message(msg)
    result = response.get('result')

    return bool(result)

async def getCallEdgeIds():
    msg = {
        "event": "sql.runSQL",
        "data": {
            "sql": f"select min(id), max(id) from Call",
            "db": "extras"
        }
    }

    layer1.log(f"Sending sql request for max/min call ids...")
    response = await message_center.send_message(msg)
    result = response.get('result')

    if not result:
        return
    
    await kvstore.set_int('min_call_id', result[0]['min(id)'])
    await kvstore.set_int('max_call_id', result[0]['max(id)'])

async def showWindow(html, prev=None, next=None, tag="main"):
    lock = asyncio.Lock()

    async with lock:
        view_msg = {
            "event": "ui.renderHTML",
            "data": {
                "html": html,
                "width": 420,
                "height": 600,
                "reopen": True,
                "windowTag": tag,

                "backEnabled": bool(await kvstore.get('history')),
            }
        }

        if prev is not None:
            view_msg["data"]["prevEnabled"] = prev # True/False
        if next is not None:
            view_msg["data"]["nextEnabled"] = next # True/False

        # with open(os.path.dirname(__file__) + '/render.html', "wt") as f:
        #     f.write(html)

        window_id = await kvstore.get_int('window_id')
        if window_id:
            view_msg['data']['windowID'] = window_id

        layer1.log("Sending view render request")
        view_resp = await message_center.send_message(view_msg)

        window_id = view_resp['windowID']
        layer1.log("HTML rendered in window: ", window_id)
        await kvstore.set_int('window_id', window_id)

async def evaluateJavaScript(script):
    window_id = await kvstore.get_int('window_id')

    if not window_id:
        return False

    script_msg = {
        "event": "ui.renderHTML",
        "data": {
            "userScript": script,
            "windowID": window_id
        }
    }
    layer1.log("Sending view script request")
    view_resp = await message_center.send_message(script_msg)
    layer1.log(view_resp)
    
    return True

async def selectCallTab(tab):
    entity = await kvstore.get('entity')
    window_id = await kvstore.get_int('window_id')

    if not entity or not entity.startswith('call:') or not window_id:
        return
    
    await evaluateJavaScript(f'selectTab("{tab}");')

async def showCallWindow(call, audio_url=None, offset=0, tab=None, no_push=False, jump_to=False):
    entity = f"call:{call['id']}"
    audio_url = audio_url or f"ext://call.audio?id={call['id']}"
    window_id = await kvstore.get_int('window_id')
    prev_entity = await kvstore.get('entity')

    # don't reload window again for the same entity
    if prev_entity == entity and window_id:
        layer1.log("Ignore window opening as it's already shown")

        if tab:
            await selectCallTab(tab)

        return

    layer1.log(f"Show window for the call {call['id']}, offset {offset}")
    # NOTE: inject transcription and summary on 'loaded' js event
    # call['transcription'] = await getTranscription(call['id'])
    # call['summary'] = await getCallSummary(call['id'])

    # workaround to remove (host), (me), etc
    # people_set = set()

    template = env.get_template("call.html")
    html = template.render(title=(call.get('title') or f"Call {call['id']}"), call=call, audio_src=audio_url, offset=offset, tab=tab)

    # TODO: need to be more specific about prev/next availability
    min_id = await kvstore.get_int('min_call_id')
    max_id = await kvstore.get_int('max_call_id')
    await showWindow(html, prev=(call['id'] > min_id), next=(call['id'] < max_id))

    if not no_push:
        await pushEntity()

    await kvstore.set('entity', entity)

    if jump_to and prev_entity != entity:
        await viewPosition(call['startDate'], frame="trailing")

async def getCall(call_id, next=False, prev=False):
    msg = {
        "event": "sql.runSQL",
        "data": {
            "sql": f"select * from Call where id = '{call_id}'",
            "db": "extras"
        }
    }

    if next:
        msg["data"]["sql"] = f"select * from Call where id > '{call_id}' order by id asc limit 1"
    elif prev:
        msg["data"]["sql"] = f"select * from Call where id < '{call_id}' order by id desc limit 1"

    layer1.log(f"Sending sql request for call {call_id}...")
    response = await message_center.send_message(msg)
    result = response.get('result')

    if not result:
        return
    
    call = result[0]

    # workaround to expand json strings
    if type(call['participants']) is str:
        call['participants'] = json.loads(call['participants'])
        
    return call

async def getCallSummary(call_id):
    msg = {
        "event": "edb.runEdgeQL",
        "data": {
            "query": "select Call {id, summary} filter .callID = <int64>$callID;",
            "variables": {
                "callID": call_id
            }
        }
    }

    layer1.log(f"Select call {call_id} summary from EdgeDB...")
    response = await message_center.send_message(msg)

    if not response:
        return
    
    summary = response[0]['summary']

    try:
        # try to unpack JSON summary
        summary = json.loads(summary)

        for t in summary:
            t['start'] = datetime.fromisoformat(t['start']).replace(tzinfo=timezone.utc).timestamp()
            t['end'] = datetime.fromisoformat(t['end']).replace(tzinfo=timezone.utc).timestamp()
    except:
        # fallback to string summary
        pass

    return summary

async def getCallList(participant):
    calls = []
    count = 1
    last_id = sys.maxsize
    participant = participant.replace("'", "''")

    while True:
        msg = {
            "event": "sql.runSQL",
            "data": {
                "sql": f"select * from Call where participants like '%{participant}%' and id < {last_id} order by id desc",
                "db": "extras"
            }
        }
        layer1.log(f"Sending sql request for calls {count}...")
        response = await message_center.send_message(msg)
        result = response.get('result')
        count += 1

        if not result:
            break
    
        calls += result
        last_id = result[-1]['id']

    # workaround to expand json strings
    for c in calls:
        if type(c['participants']) is str:
            c['participants'] = json.loads(c['participants'])
        
    return calls

async def showPersonWindow(name, no_push=False):
    person = {
        'name': name,
        'calls': await getCallList(name)
    }

    names = name.split()

    if len(names) > 1:
        person['initials'] = (names[0][0] + names[1][0]).upper()
    else:
        person['initials'] = name[0].upper()

    template = env.get_template("person.html")
    html = template.render(title=name, person=person)

    await showWindow(html)

    if not no_push:
        await pushEntity()

    await kvstore.set('entity', f"person:{name}")

    # Analytics
    analytics_msg = {
        "event": "analytics.track",
        "data": {
            "event": "Open Person Window"
        } 
    }
    await message_center.send_message(analytics_msg)

async def pushEntity():
    entity = await kvstore.get('entity')

    if not entity:
        return

    history = await kvstore.get_json('history') or []

    if history and history[-1] == entity:
        return
    
    history.append(entity)
    await kvstore.set_json('history', history)

async def popEntity():
    history = await kvstore.get_json('history')

    if not history:
        return
    
    entity = history.pop()
    if history:
        await kvstore.set_json('history', history)
    else:
        await kvstore.remove('history')
    return entity

async def showEntity(entity, no_push=False):
    e_type, e_id = entity.split(':', 1)

    if e_type == 'person':
        await showPersonWindow(e_id, no_push=no_push)
        return
    
    if e_type == 'call':
        call = await getCall(e_id)
        if call:
            await showCallWindow(call, no_push=no_push, jump_to=True)
        return

async def updatePlayerPosition(timestamp):
    ignore_seek = await kvstore.get('ignore_seek')
    if ignore_seek:
        layer1.log("Too soon, ignore updated position...")
        return

    script = f"track.currentTime = {timestamp} - startTime;"
    await evaluateJavaScript(script)

async def viewPosition(timestamp, frame="closest"):
    seek_msg = {
        "event": "ui.viewPosition",
        "data": {
            "timestamp": timestamp,
            "frame": frame
        }
    }
    view_resp = await message_center.send_message(seek_msg)
    await kvstore.set("ignore_seek", "true", 2)
    layer1.log("Position set: ", view_resp)

async def setCallTitle(call_id, title):
    seek_msg = {
        "event": "calls.setTitle",
        "data": {
            "callID": call_id,
            "title": title
        }
    }
    view_resp = await message_center.send_message(seek_msg)
    layer1.log("Title update:", view_resp)

async def handleJSCallback(msg):
    if 'log' in msg:
        layer1.log(*msg['log'])
        return

    loaded = msg.get('loaded')

    if loaded:
        if loaded == await kvstore.get('entity') and loaded.startswith("call:"):
            call_id = int(loaded.split(":")[-1])
            call = await getCall(call_id)
            await injectTranscription(call)
            await injectSummary(call=call)
        return

    timestamp = msg.get('timeUpdate')

    if timestamp:
        await viewPosition(timestamp, frame=msg.get('frame', 'closest'))
        return

    participant = msg.get('participant')

    if participant:
        await showPersonWindow(participant)
        return

    call = msg.get('call')

    if call:
        await showCallWindow(call, jump_to=True)
        return

    tab = msg.get('tab')

    if tab:
        await kvstore.set('tab', tab)
        return

    summary = msg.get('summary')

    if summary:
        await createSummary(summary)
        return

    call_title = msg.get('title')
    call_id = msg.get('callId')

    if call_title and call_id:
        await setCallTitle(call_id, call_title)
        return

    layer1.log('Unhandled message:', msg)

async def createSummary(call_id):
    layer1.log('Create summary for call:', call_id)

    call = await getCall(call_id)

    if not call.get('endDate'):
        layer1.log("Call id not finished:", call_id)
        return
    
    if call['endDate'] - call['startDate'] < 20:
        layer1.log("Call is too short:", call_id)
        return

    if await checkTranscription(call_id) == False:
        layer1.log("There's no transcription for call:", call_id)
        return

    script_msg = {
        "event": "layerScript.run",
        "data": {
            "scriptID": "0FFC00D4-4535-405F-9C6F-B10936E595EE",
            "scriptInput": str(call_id)
        }
    }
    response = await message_center.send_message(script_msg)
    summary = response['summary']

    layer1.log("Saving summary to EdgeDB")

    save_msg = {
        "event": "edb.runEdgeQL",
        "data": {
            "query": "update Call filter .callID = <int64>$callID set { summary := <str>$summary };",
            "variables": {
                "callID": call_id,
                "summary": summary
            }
        }
    }
    summary_resp = await message_center.send_message(save_msg)
    layer1.log(summary_resp)

    if await injectSummary(call_id=call_id):
        return

    layer1.log("Trigger UI notification...")
    msg = {
        "event": "ui.showNotification",
        "data": {
            "text": "Call summary is ready.\nClick here to view.",
            "action": {
                # "title": "See summary »",
                "data": f"summary:{call_id}"
            }
        }
    }
    response = await message_center.send_message(msg)
    layer1.log("Notification id:", response)

async def injectSummary(call=None, call_id=None):
    template = env.get_template("summary.html")
    if call is None:
        call = await getCall(call_id)
    else:
        call_id = call['id']

    # TODO: prepare summary instead of making query
    call['summary'] = await getCallSummary(call_id)
    html = template.render(call=call).replace('`', '\`')

    if await kvstore.get('entity') != f"call:{call_id}":
        return False

    layer1.log("Inject summary for call", call_id)

    await evaluateJavaScript(f"""
        (() => {{ 
            document.querySelector(".summary-content").innerHTML = `{html}`;
            updateTopics();
            onTimeUpdate(track.currentTime);
        }})();
    """)

    return True

async def injectTranscription(call):
    template = env.get_template("transcription.html")
    # call = await getCall(call_id)
    call_id = call['id']
    call['transcription'] = await getTranscription(call_id)
    html = template.render(call=call).replace('`', '\`')

    if await kvstore.get('entity') != f"call:{call_id}":
        return False

    layer1.log("Inject transcription for call", call_id)

    await evaluateJavaScript(f"""
        (() => {{ 
            document.querySelector(".transcript-items").innerHTML = `{html}`;
            updateTranscript();
            onTimeUpdate(track.currentTime);
        }})();
    """)

    return True

async def handleNotificationCallback(msg):
    not_id = msg['notificationID']
    layer1.log('Notification callback:', not_id)
    action = msg['action'].get('data')

    if not action:
        return
    
    if action.startswith("summary:"):
        call_id = int(action.split(":")[-1])
        call = await getCall(call_id)
        await showCallWindow(call, tab="summary", jump_to=True)
        return

# Handler for incoming events on the 'ui' channel
async def ui_handler(channel, event, msg):
    if event == 'positionDidChange':
        await updatePlayerPosition(msg.get('timestamp'))
        return

    layer1.log(f'Unhandled event: {event}:\n', json.dumps(msg, indent=4))

#     elif event == 'notificationCallback':
#         await handleNotificationCallback(msg)

# Handler for incoming events on the 'message' channel
async def msg_handler(channel, event, msg):
    # print(f"{event}:\n", json.dumps(msg, indent=4))

    if event == 'callCopilot':
        await showCallWindow(msg.get('call'), audio_url=msg.get('source'), offset=msg.get('offset', 0))
        return

    if event == 'callSummary':
        await createSummary(msg.get('call')['id'])
        return

    if event == 'jsEventFired':
        await handleJSCallback(msg)
        return
    
    if event == 'notificationCallback':
        await handleNotificationCallback(msg)
        return

    if event == 'goBack':
        entity = await popEntity()
        if entity:
            await showEntity(entity, no_push=True)
        return
    
    if event == 'nextItem':
        entity = await kvstore.get('entity')
        if not entity:
            return
        if entity.startswith("call:"):
            call_id = int(entity.split(':')[-1])
            call = await getCall(call_id, next=True)
            if call:
                tab = await kvstore.get('tab')
                await showCallWindow(call, tab=tab, jump_to=True)
        return
    
    if event == 'previousItem':
        entity = await kvstore.get('entity')
        if not entity:
            return
        if entity.startswith("call:"):
            call_id = int(entity.split(':')[-1])
            call = await getCall(call_id, prev=True)
            if call:
                tab = await kvstore.get('tab')
                await showCallWindow(call, tab=tab, jump_to=True)
        return
    
    # if event == 'settings':
    #     await showSettings()
    #     return

    if event == 'windowWillClose':
        if msg['windowID'] == await kvstore.get_int('window_id'):
            await kvstore.remove('window_id')
            await kvstore.remove('entity')
            await kvstore.remove('history')
        return

# Handler for incoming events on the 'call' channel
async def call_handler(channel, event, msg):
    layer1.log(f"{event}:\n", json.dumps(msg, indent=4))

    if event == 'callDidStart':
        await kvstore.set_int('max_call_id', msg['id'])

    if event == 'callDidEnd':
        await createSummary(msg['id'])

loop.create_task(register())
loop.create_task(set_locale())
loop.create_task(getCallEdgeIds())
message_center.subscribe('ui', ui_handler)
message_center.subscribe('messages', msg_handler)
message_center.subscribe('calls', call_handler)

layer1.log("Waiting for extension triggers...")
message_center.run() # Will run forever
