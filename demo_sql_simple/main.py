import remynd
import asyncio
import json
import uuid
import re
import os

# Create a MessageCenter instance
loop = asyncio.get_event_loop()
message_center = remynd.MessageCenter(loop)
kvstore = remynd.Dictionary(message_center.extension_id)

async def showWindow(query, result=''):
    html = f"""
    <html><body style="background-color: #1f1f1f; color: white; font-family: 'SF Pro'">
    <h2>SQL Playground</h2>
    <form id="form">
    <label for="query" style="margin: 0.5em;">Query:</label>
    <br>
    <textarea name="query" style="width: 90%; height: 20%; margin: 0.5em; font-family: courier; font-size: 0.85em;">{query}</textarea>
    <br>
    <button type="submit" style="margin: 0.5em; padding: 1em;">EXECUTE »</button>
    </form>
    <label style="margin: 0.5em;">Result:</label>
    <br>
    <p style="font-size: 1em;">
        <code style="margin: 0.75em; width: 100%; white-space: pre-wrap;">{result or 'undefined'}</code>
    </p>
    </body></html>
    """

    # https://developer.mozilla.org/en-US/docs/Web/API/FormDataEvent
    script = """
    const formElem = document.getElementById("form")
    formElem.addEventListener("submit", event => {
        event.preventDefault();
        const json = Object.fromEntries(new FormData(formElem));
        window.webkit.messageHandlers.remynd.postMessage(json)
    });
    """
    view_msg = {
        "event": "ui.renderHTML",
        "data": {
            "html": html,
            "userScript": script,
            "width": 900,
            "height": 500
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

async def handleJSCallback(msg):
    print('Execute:', msg)
    query = msg.get('query')

    if not query:
        return
    
    msg = {
        "event": "sql.runSQL",
        "data": {
            "sql": query
        }
    }
    remynd.log("Sending sql request...")
    response = await message_center.send_message(msg)
    result = response.get('result')

    if result is None:
        print("Response: ", response)
        return

    json_text = json.dumps(result, indent=4)
    # workaround to decode \uXXXX uncicode symbols
    codepoint = re.compile(r'(\\u[0-9a-fA-F]{4})')
    def replace(match):
        return chr(int(match.group(1)[2:], 16))
    json_text = codepoint.sub(replace, json_text)

    await showWindow(query, json_text)

# Handler for incoming events on the 'messages' channel
async def msg_handler(channel, event, msg):
    if event == 'jsEventFired':
        await handleJSCallback(msg)

loop.create_task(showWindow('SELECT * FROM FrameOCR LIMIT 10;'))
message_center.subscribe('messages', msg_handler)
remynd.log("Waiting for extension triggers...")
message_center.run() # Will run forever
