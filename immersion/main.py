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

# async def immersing_task(rpm):
#     # await kvstore.remove("state")
#     # await kvstore.remove("frame_count")
#     await kvstore.get_int('last_timestamp')

#     while True:
#         await asyncio.sleep(5)

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
        if ocr.get("appName"):
            text += f"Application: {ocr['appName']}\n"
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
            'appName': ocr_list[-1].get('appName'),
            'timestamp': ocr_list[-1].get('timestamp'),
            'summary': response['text']
        })

        template = env.get_template("activity.html")
        html = template.render(activity=activity)

        await showWindow(html)
        await kvstore.set_json("activity", activity)

    await kvstore.remove("state")

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

# Handler for incoming events on the 'recorder' channel
async def recorder_handler(channel, event, msg):
    if event == 'didCaptureOCR':
        await handleDidCaptureOCR(msg)

# loop.create_task(immersing_task(1))
# message_center.subscribe('ui', ui_handler)
message_center.subscribe('recorder', recorder_handler)
layer1.log("Waiting for extension triggers...")
message_center.run() # Will run forever
