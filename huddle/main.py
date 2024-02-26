import layer1
import asyncio
import json
import uuid
import objectpath

# Create a MessageCenter instance
loop = asyncio.get_event_loop()
message_center = layer1.MessageCenter(loop)

poll_task = None

async def show_recording_msg(isRecording):
    text =  "Recording started" if isRecording else "Recording ended"
    html = """
    <html><body>
    <h1>Slack Huddle</h1>
    <p>{text}</p>
    </body></html>
    """.format(text=text)
    view_msg = {
        "event": "ui.renderHTML",
        "data": {
            "html": html
        }
    }
    layer1.log("Sending view render request")
    status = await message_center.send_message(view_msg)
    layer1.log("Render status: ", status)

async def start_recording(pid):
    layer1.log("Starting huddle recording")
    msg = {
        'event': 'recorder.startCallRecording',
        'data': {
            'pid': pid
        }
    }
    resp = await message_center.send_message(msg)
    if 'error' in resp:
        layer1.log("Error starting huddle recording: ", resp['error'])
    else:
        await show_recording_msg(True)

async def stop_recording(pid):
    layer1.log("Stopping huddle recording")
    msg = {
        'event': 'recorder.stopCallRecording',
        'data': {
            'pid': pid
        }
    }
    await message_center.send_message(msg)
    await show_recording_msg(False)

# Electron apps need to have AX enabled before any window elements become visible
async def enable_electron_ax(pid):
    msg = {
        'event': 'ax.setAttributeValue',
        'data': {
            'pid': pid,
            'attribute': 'AXManualAccessibility',
            'boolValue': True
        }
    }
    await message_center.send_message(msg)

async def find_huddle_controls(pid):
    msg = {
        'event': 'ax.getProcessTree',
        'data': {
            'pid': pid
        }
    }
    tree_resp = await message_center.send_message(msg)
    windows = tree_resp['windows']
    for window in windows:
        window_tree = objectpath.Tree(window)
        # Note: when NOT on a call, there is an invisible element with label "Huddle".
        # When on a call, the element's label becomes "Huddle in XYZ...", but it has a child with label "Huddle controls".
        # huddle_controls = window_tree.execute("$..children[@.description is 'Huddle' or @.description is 'Huddle controls']")
        huddle_controls = window_tree.execute("$..children[@.description is 'Huddle controls']")
        for entry in huddle_controls:
            if 'uuid' in entry:
                return entry['uuid']

async def find_gallery(uuid):
    msg = {
        'event': 'ax.getNodeTree',
        'data': {
            'uuid': uuid
        }
    }
    tree_resp = await message_center.send_message(msg)
    huddle_controls = tree_resp['node']
    controls_tree = objectpath.Tree(huddle_controls)
    gallery = controls_tree.execute("$..children[@.description is 'Gallery']")
    for entry in gallery:
        if 'uuid' in entry:
            return True
    return False

async def poll_slack_ax(pid):
    # huddle_controls = None
    on_call = False

    # Must enable AX manually for electron apps
    await enable_electron_ax(pid)
    
    while True:
        layer1.log("Polling Slack...")
        try:
            huddle_controls = await find_huddle_controls(pid)
            if huddle_controls:
                layer1.log("Huddle controls found")
                if not on_call:
                    # Huddle was just started/discovered; start recording now
                    await start_recording(pid)
                    on_call = True
            else:
                layer1.log("Huddle controls not found")
                if on_call:
                    # Huddle just ended; stop recording now
                    await stop_recording(pid)
                    on_call = False
            # if huddle_controls == None:
            #     # Find top-level huddle controls in full AX tree
            #     layer1.log("Looking for Huddle controls container...")
            #     huddle_controls = await find_huddle_controls(pid)
            # if huddle_controls:
            #     layer1.log("Huddle controls container found")
            #     # Check for Gallery within huddle controls element
            #     is_call = await find_gallery(huddle_controls)
            #     layer1.log("Call gallery discovered: ", is_call)
            #     if is_call and not on_call:
            #         # Huddle was just started; start recording now
            #         await start_recording(pid)
            #     elif on_call and not is_call:
            #         # Huddle just ended; stop recording now
            #         await stop_recording(pid)
            #     on_call = is_call
            # else:
            #     layer1.log("Huddle controls container not found")
        except Exception as e:
            layer1.log(e)
            # Exception was raised; likely the AX element became invalid
            # Force a full AX tree refresh
            huddle_controls = None

        # Wait before polling again
        await asyncio.sleep(5)

async def check_slack_running():
    layer1.log("Checking for existing Slack instance...")
    def is_slack(app):
        return 'bundleID' in app and app['bundleID'] == 'com.tinyspeck.slackmacgap'
    msg = {
        "event": "system.getRunningApps"
    }
    resp = await message_center.send_message(msg)
    apps = resp['runningApps']
    slack_proc = next(filter(lambda app: is_slack(app), apps), None)
    if slack_proc:
        # Slack is running; start polling AX now
        layer1.log("Slack is running, will start polling")
        global poll_task
        poll_task = loop.create_task(poll_slack_ax(slack_proc['pid']))
    else:
        layer1.log("Slack not running, will observe app launch")

async def sys_handler(channel, event, msg):
    if event == 'applicationDidLaunch':
        if 'bundleID' in msg and msg['bundleID'] == 'com.tinyspeck.slackmacgap':
            # Slack launched; poll huddle status
            layer1.log("Slack launched")
            global poll_task
            pid = msg['pid']
            poll_task = loop.create_task(poll_slack_ax(pid))
    elif event == 'applicationDidTerminate':
        if 'bundleID' in msg and msg['bundleID'] == 'com.tinyspeck.slackmacgap':
            # Slack no longer running; cancel polling
            layer1.log("Slack terminated")
            poll_task.cancel()

# Check once at startup if Slack is already running
# loop.create_task(check_slack_running())
loop.create_task(check_slack_running())

# Register event handler and start the message center
message_center.subscribe('system', sys_handler)
layer1.log("Waiting for Slack huddles...")
message_center.run() # Will run forever