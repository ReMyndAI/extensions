import remynd
import asyncio
import json
import uuid
import datetime
import os

# Create a MessageCenter instance
loop = asyncio.get_event_loop()
message_center = remynd.MessageCenter(loop)
kvstore = remynd.Dictionary(message_center.extension_id)

async def handleNotificationCallback(msg):
    not_id = msg['notificationID']
    remynd.log('Notification callback: ', not_id)
    timestamps = msg['action'].get('data')
    if timestamps is None:
        return

    json_obj = json.loads(timestamps)
    date_strings = map(lambda d: datetime.datetime.fromtimestamp(d).strftime("%d/%m/%Y, %H:%M:%S"), json_obj)
    participants = "</li><li>".join(date_strings)
    html = f"""
    <html><body>
    <h2>Captured Frames</h2>
    <ul>
    <li>{participants}</li>
    </ul>
    </body></html>
    """
    view_msg = {
        "event": "ui.renderHTML",
        "data": {
            "html": html,
            "width": 400,
            "height": 600
        }
    }
    remynd.log("Sending view render request")
    view_resp = await message_center.send_message(view_msg)
    window_id = view_resp['windowID']
    remynd.log("Frame list rendered in window: ", window_id)

async def handleDidCaptureFrame(msg):
    print('Frame captured!', msg)
    
    frame_count = await kvstore.increment('frame_count')
    print('Frame count:', frame_count)

    frame_timestamps = await kvstore.get_json('frame_timestamps')    
    frame_timestamps = frame_timestamps or []
    frame_timestamps.append(int(msg['timestamp']))
    await kvstore.set_json('frame_timestamps', frame_timestamps)

    if frame_count < 10:
        return
    
    await kvstore.remove('frame_count')
    remynd.log("Trigger UI notification...")
    
    msg = {
        "event": "ui.showNotification",
        "data": {
            "text": "10 frames captured!\nClick here to show timestamps.",
            "action": {
                "data": json.dumps(frame_timestamps)
            }
        }
    }
    response = await message_center.send_message(msg)
    print("Notification id: ", response)

# Handler for incoming events on the 'ui' channel
async def ui_handler(channel, event, msg):
    if event == 'notificationCallback':
        await handleNotificationCallback(msg)

# Handler for incoming events on the 'recorder' channel
async def recorder_handler(channel, event, msg):
    if event == 'didCaptureFrame':
        await handleDidCaptureFrame(msg)

message_center.subscribe('ui', ui_handler)
message_center.subscribe('recorder', recorder_handler)
remynd.log("Waiting for extension triggers...")
message_center.run() # Will run forever
