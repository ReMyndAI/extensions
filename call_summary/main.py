import layer1
import asyncio
import json
import uuid
import sys

# Create a MessageCenter instance
loop = asyncio.get_event_loop()
message_center = layer1.MessageCenter(loop)

# Business logic for generating call summaries
async def handleCallDidEnd(msg):
    layer1.log('Call ended: ', msg['callID'])
    script_msg = {
        "event": "layerScript.run",
        "data": {
            "scriptID": "0FFC00D4-4535-405F-9C6F-B10936E595EE",
            # "scriptInput": str(msg['callID'])
            "scriptInput": "1706636386"
        }
    }
    layer1.log("Sending summary request")
    summary_msg = await message_center.send_message(script_msg)
    layer1.log("Got summary result")
    summary = summary_msg['summary']
    layer1.log("Saving summary to EdgeDB")
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
    layer1.log(summary_resp)

# Handler for incoming events on the 'calls' channel
async def call_handler(channel, event, msg):
    if event == 'callDidEnd':
        await handleCallDidEnd(msg)

# Register event handler and start the message center
message_center.subscribe('calls', call_handler)
layer1.log("Waiting for video calls...")
message_center.run() # Will run forever
