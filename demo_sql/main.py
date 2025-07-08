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

async def showWindow(query, db=None, result=''):
    window_id = await kvstore.get_int('window_id')

    if window_id and await updateWindow(window_id, result):
        remynd.log("Window content updated")
        return

    html = f"""
    <html>
    <head>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/json.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/sql.min.js"></script>
    <style>
        body {{
            background-color: #1f1f1f;
            color: white;
            font-family: 'SF Pro';
        }}

        .input-area {{
            position: relative;
            outline: none;
            height: 20%;
            background-color: #282c34;
            margin: 1em;
        }}

        .stack {{
            position: absolute;
            display: inline-block;
            padding: 1em;
            bottom: 0;
            top: 0;
            right: 0;
            left: 0;
        }}

        .background {{
            background-color: #282c34;
            padding: 1em;
        }}

        .preview {{
            background: transparent;
            z-index: 3;
        }}

        .textarea {{
            color: transparent;
            background: none;
            z-index: 3;

            margin: 0;
            border: none;
            border-radius: 0;
            outline: none;
            appearance: none;
        }}

        .cursor {{
            background: none;
            z-index: 1;
    
            margin: 0;
            border: none;
            border-radius: 0;
            outline: none;
            appearance: none;
        }}

        .preview, textarea {{
            font-size: 0.85em;
            font-weight: 200;
            font-family: 'Courier New', Courier, monospace;
            resize: none;
        }}
    </style>
    </head>
    <body>
        <h2>SQL Playground</h2>
        <form id="form">
            <label for="query" style="margin: 0.5em;">Query:</label>
            <br>
            <div class="input-area">
                <textarea name="query" id="query" class="stack textarea" autofocus>{query}</textarea>
                <textarea id="cursor" class="stack cursor"></textarea>
                <pre><code id="preview" class="stack preview language-sql">{query}</code></pre>
            </div>        
            <br>
            <label for="db" style="margin: 0.5em;">Database:</label>
            <input type="radio" id="main" name="db" value="main"{' checked' if db != 'extras' else ''} />
            <label for="main">Main</label>
            <input type="radio" id="extras" name="db" value="extras"{' checked' if db == 'extras' else ''} />
            <label for="extras">Extras</label>
            <br>
            <button type="submit" style="margin: 0.5em; padding: 1em;">EXECUTE »</button>
        </form>
        <label style="margin: 0.5em;">Result:</label>
        <br>
        <p style="font-size: 1em;">
            <pre><code class="language-json" id="result" style="margin: 0.75em; white-space: pre-wrap; word-wrap: break-word;">{result or '"undefined"'}</code></pre>
        </p>
        <script>
            var inputArea = document.getElementById("query");
            var outputArea = document.getElementById("preview");
            var cursor = document.getElementById("cursor");

            outputArea.addEventListener("click", function (event) {{
                inputArea.style.zIndex = 4;
            }}, false);

            inputArea.addEventListener("input", function (event) {{
                outputArea.innerHTML = inputArea.value;
                inputArea.style.zIndex = 4;
                refreshHighlighting();
            }}, false);

            // Refresh highlighting when blured focus from textarea.
            outputArea.addEventListener("blur", function (event) {{
                refreshHighlighting();
            }}, false)

            function refreshHighlighting() {{
                outputArea.removeAttribute("data-highlighted");
                hljs.highlightBlock(outputArea);
                inputArea.style.zIndex = 0;
            }}

            refreshHighlighting();
        </script>
    </body>
    </html>
    """

    # https://developer.mozilla.org/en-US/docs/Web/API/FormDataEvent
    script = """
    const formElem = document.getElementById("form")
    formElem.addEventListener("submit", event => {
        event.preventDefault();
        const json = Object.fromEntries(new FormData(formElem));
        window.webkit.messageHandlers.remynd.postMessage(json);
    });
    hljs.highlightAll();
    """
    view_msg = {
        "event": "ui.renderHTML",
        "data": {
            "html": html,
            "userScript": script,
            "width": 900,
            "height": 500,
            "title": "Demo Extension (SQL)"
        }
    }

    if window_id:
        view_msg['data']['windowID'] = window_id

    remynd.log("Sending view render request")
    view_resp = await message_center.send_message(view_msg)
    window_id = view_resp['windowID']
    remynd.log("HTML rendered in window: ", window_id)
    await kvstore.set_int('window_id', window_id)

async def updateWindow(window_id, result=''):
    result = result.replace('\\', '\\\\')
    result = result.replace('`', '\`')
    script = f"""
    (function() {{
    const resultElem = document.getElementById("result");
    resultElem.textContent = `{result}`;
    resultElem.removeAttribute("data-highlighted");
    hljs.highlightBlock(resultElem);
    }})()
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
    view_resp = await message_center.send_message(view_msg)

    if view_resp.get('windowID') == window_id:
        remynd.log("JS executed succefully in window: ", window_id)
        return True
    
    remynd.log("Failed to execute js in window: ", window_id, view_resp)
    return False

async def handleJSCallback(msg):
    print('Execute:', msg)
    query = msg.get('query')
    db = msg.get('db') or 'main'

    if not query:
        return
    
    msg = {
        "event": "sql.runSQL",
        "data": {
            "sql": query,
            "db": db
        }
    }
    remynd.log("Sending sql request...")
    response = await message_center.send_message(msg)
    result = response.get('result')

    if result is None:
        print("Response: ", response)
        json_text = json.dumps(response, indent=4)
    
    else:
        json_text = json.dumps(result, indent=4)
        # workaround to decode \uXXXX uncicode symbols
        codepoint = re.compile(r'(\\u[0-9a-fA-F]{4})')
        def replace(match):
            return chr(int(match.group(1)[2:], 16))
        json_text = codepoint.sub(replace, json_text)

    await showWindow(query, db=db, result=json_text)

# Handler for incoming events on the 'messages' channel
async def msg_handler(channel, event, msg):
    if event == 'jsEventFired':
        await handleJSCallback(msg)

loop.create_task(showWindow('SELECT * FROM FrameOCR LIMIT 10;'))
message_center.subscribe('messages', msg_handler)
remynd.log("Waiting for extension triggers...")
message_center.run() # Will run forever
