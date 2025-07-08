import remynd
import asyncio
import json
import uuid
import sys

# Create a MessageCenter instance
loop = asyncio.get_event_loop()
message_center = remynd.MessageCenter(loop)

# Business logic for generating call summaries
async def handleCallDidEnd(msg):
    remynd.log('Call ended: ', msg['callID'])
    script_msg = {
        "event": "layerScript.run",
        "data": {
            "scriptID": "0FFC00D4-4535-405F-9C6F-B10936E595EE",
            # "scriptInput": str(msg['callID'])
            "scriptInput": "1706636386"
        }
    }
    remynd.log("Sending summary request")
    summary_msg = await message_center.send_message(script_msg)
    remynd.log("Got summary result")
    summary = summary_msg['summary']
    remynd.log("Saving summary to EdgeDB")
    save_msg = {
        "event": "edb.runEdgeQL",
        "data": {
            "query": "update Call filter .callID = <int64>$callID set { summary := <str>$summary };",
            "variables": {
                "callID": msg['callID'],
                "summary": summary
            }
        }
    }
    summary_resp = await message_center.send_message(save_msg)
    remynd.log(summary_resp)

# Handler for incoming events on the 'calls' channel
async def call_handler(channel, event, msg):
    if event == 'callDidEnd':
        await handleCallDidEnd(msg)

# Register event handler and start the message center
message_center.subscribe('calls', call_handler)
remynd.log("Waiting for video calls...")
message_center.run() # Will run forever
