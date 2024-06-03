import layer1
import asyncio
import json
import uuid
import time
import os
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

def date_str_hr(ts):
    dstr = datetime.fromtimestamp(ts).strftime("%x")
    if datetime.fromtimestamp(get_timestamp()).strftime("%x") == dstr:
        return "Today"
    return dstr

def time_str(ts):
    return datetime.fromtimestamp(ts).strftime("%X")

def encode_image(path):
    with open(os.path.dirname(__file__) + '/' + path, "rb") as f:
        return b64encode(f.read()).decode('ascii')
    
env.globals['encodeImage'] = encode_image
env.globals['getTimestamp'] = get_timestamp
env.globals['dateStr'] = date_str
env.globals['timeStr'] = time_str
env.globals['dumps'] = json.dumps

async def register():
    layer1.log("Extension ID:", message_center.extension_id)

    reg_msg = {
        "event": "extension.register",
        "data": {
            "capabilities": {
                "standalone": [
                    {
                        "title": "Activity Log",
                        "event": "launch",
                    },
                    {
                        "title": "Perform OCR",
                        "event": "performOCR",
                    }
                ],
            }
        }
    }

    reg_resp = await message_center.send_message(reg_msg)
    layer1.log("Registration:", json.dumps(reg_resp, indent=4))

    await kvstore.remove('window_id')
    await kvstore.remove('ocr_list')
    await kvstore.remove('state')

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
                "windowTag": tag
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
        await kvstore.remove("hidden")

async def renderActivity():
    activity = await kvstore.get_json("activity") or []

    dates = []

    for a in activity:
        date = date_str_hr(a['timestamp'])
        a['date'] = date
        if not dates or dates[-1] != date:
             dates.append(date)

    image_data = None
    day_spent = 0.0
    if activity:
        bundle_id = activity[-1].get("bundle_id")
        if bundle_id:
            image_data = await kvstore.get(f"bundle:{bundle_id}")

        for a in activity:
            if a['date'] == activity[-1]['date']:
                try:
                    day_spent += float(a['cost'])
                except:
                    pass

    image_data = image_data or encode_image("assets/images/5a3187eb-90c8-4a0e-bf98-bb293ba809a6.png")
    template = env.get_template("activity.html")
    html = template.render(activity=activity, dates=dates, icon=image_data, cost=f"{day_spent:.03f}")
    await showWindow(html)

async def ai_prompt_task():
    if await kvstore.get("state"):
        layer1.log('AI is working, enqueue this OCR message')
        return

    await kvstore.set("state", "running")

    ocr_list = await kvstore.get_json("ocr_list")

    if not ocr_list:
        layer1.log('OCR data is empty, skipping')
        return
    
    await kvstore.remove("ocr_list")
    
    text = ""

    for ocr in ocr_list:
        if ocr.get("app_name"):
            text += f"Application: {ocr['app_name']}\n"
        if ocr.get("title"):
            text += f"Title: {ocr['title']}\n"
        if ocr.get("url"):
            text += f"URL: {ocr['url']}\n"

        text += f"{ocr['text']}\n\n"

    msg = {
        "event": "ai.query",
        "data": {
            "instructions": "Some OCR data from one or more user opened windows will be provided, including application names, optional window titles and optional visited URLs for browser windows. Identify the context on what the user is currently working on and generate a short summary in one impersonal sentence without subject. The result should be a formatted string with line breaks inserted so that there's no more than 35 letters in each line.",
            "text": text
        }
    }
    response = await message_center.send_message(msg)
    print("AI response: ", response)

    layer1.log("Got AI reply, trigger UI notification...")

    if 'text' in response:    
        # msg = {
        #     "event": "ui.showNotification",
        #     "data": {
        #         "text": response['text'],
        #         # "action": {
        #         #     "data": json.dumps(frame_timestamps)
        #         # }
        #     }
        # }
        # response = await message_center.send_message(msg)
        # print("Notification id: ", response)

        activity = await kvstore.get_json("activity") or []
        activity.append({
            'app_name': ocr_list[-1].get('app_name'),
            'bundle_id': ocr_list[-1].get('bundle_id'),
            'timestamp': ocr_list[-1].get('timestamp'),
            'summary': response['text'],
            'cost': f"{response.get('cost', 0):.03f}"
        })

        await kvstore.set_json("activity", activity)

        if not await kvstore.get("hidden"):
            await renderActivity()

    await kvstore.remove("state")

async def performOCR(position):
    layer1.log("OCR triggered:", position / 600)

    msg = {
        "event": "recorder.getFrameOCR",
        "data": {
            "position": position
        }
    }
    response = await message_center.send_message(msg)

    if not response.get('text'):
        layer1.log("Got empty OCR result")
        return
    
    layer1.log("Got OCR result, trigger AI task...")

    ocr_list = await kvstore.get_json('ocr_list') or []
    ocr_list.append({
        'id': int(response.get('timestamp')),
        'timestamp': response.get('timestamp'),
        'app_name': response.get('appName'),
        'bundle_id': response.get('bundleId'),
        'text': response['text'],
        'title': response.get('title'),
        'url': response.get('url')
    })

    bundle_id = response.get('bundleId')
    app_icon = response.get('appIcon')

    if bundle_id and app_icon:
        await kvstore.set(f"bundle:{bundle_id}", app_icon)

    await kvstore.set_json('ocr_list', ocr_list)
    await ai_prompt_task()

# async def handleNotificationCallback(msg):
#     not_id = msg['notificationID']
#     layer1.log('Notification callback: ', not_id)
#     timestamps = msg['action'].get('data')
#     if timestamps is None:
#         return

#     json_obj = json.loads(timestamps)
#     date_strings = map(lambda d: datetime.datetime.fromtimestamp(d).strftime("%d/%m/%Y, %H:%M:%S"), json_obj)
#     participants = "</li><li>".join(date_strings)
#     html = f"""
#     <html><body>
#     <h2>Captured Frames</h2>
#     <ul>
#     <li>{participants}</li>
#     </ul>
#     </body></html>
#     """
#     view_msg = {
#         "event": "ui.renderHTML",
#         "data": {
#             "html": html,
#             "width": 400,
#             "height": 600
#         }
#     }
#     layer1.log("Sending view render request")
#     view_resp = await message_center.send_message(view_msg)
#     window_id = view_resp['windowID']
#     layer1.log("Frame list rendered in window: ", window_id)

async def handleDidCaptureOCR(msg):
    print('OCR captured!', msg)

    ocr_list = await kvstore.get_json('ocr_list') or []
    ocr_list.append(msg)

    await kvstore.set_json('ocr_list', ocr_list)
    await ai_prompt_task()

# Handler for incoming events on the 'ui' channel
# async def ui_handler(channel, event, msg):
#     if event == 'notificationCallback':
#         await handleNotificationCallback(msg)

# Handler for incoming events on the 'message' channel
async def msg_handler(channel, event, msg):
    # print(f"{event}:\n", json.dumps(msg, indent=4))

    if event == 'launch':
        await renderActivity()
        return

    if event == 'performOCR':
        last_timestamp = await kvstore.get_json("last_timestamp")
        if not last_timestamp:
            return
        await performOCR(int(last_timestamp['position']))
        return
    
    if event == 'windowWillClose':
        await kvstore.remove('window_id')
        await kvstore.set("hidden", 1)
        return

# Handler for incoming events on the 'recorder' channel
async def recorder_handler(channel, event, msg):
    if event == 'didCaptureFrame':
        await kvstore.set_json("last_timestamp", msg)
        return

    if event == 'didCaptureOCR':
        await handleDidCaptureOCR(msg)

loop.create_task(register())
# message_center.subscribe('ui', ui_handler)
message_center.subscribe('messages', msg_handler)
message_center.subscribe('recorder', recorder_handler)
layer1.log("Waiting for extension triggers...")
message_center.run() # Will run forever
