"""UNO Q App Lab prototype: physical button + unchanged MindWave pipeline -> BLE.

Requires this repository on the Q, bless, the board's arduino.app_utils, and a paired
headset serial port in NEUROPACE_HEADSET_PORT. Hardware validation is still required.
"""
import asyncio
import json
import os
import threading

from arduino.app_utils import App, Bridge
from bless import BlessServer, GATTAttributePermissions, GATTCharacteristicProperties
from mindwave import MindWaveSource, Pipeline
from neuropace.totem.uno_q import COMMANDS, EVENTS, SERVICE, RelayFrame


async def main():
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue(maxsize=16)
    pipeline = Pipeline(MindWaveSource(os.environ["NEUROPACE_HEADSET_PORT"]))
    sequence = 0
    stopped = threading.Event()

    def enqueue(message):
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(message)

    def frame_ready(frame):
        # Preserve the pipeline's feature math and quality gates; send one frame/sec.
        payload = RelayFrame.model_validate(frame.to_dict()).model_dump()
        loop.call_soon_threadsafe(enqueue, {"type": "frame", "frame": payload})

    last_count = None

    def poll_button():
        nonlocal last_count
        if stopped.wait(.05):
            return
        try:
            count = int(Bridge.call("neuropace_button_count"))
            if last_count is not None and count > last_count:
                for _ in range(min(count - last_count, 8)):
                    loop.call_soon_threadsafe(enqueue, {"type": "tap"})
            last_count = count
            # Status is refreshed below rather than sending it on every poll.
            button_state["ready"] = True
        except Exception:
            last_count = None
            button_state["ready"] = False

    button_state = {"ready": False}
    server = BlessServer(name="NeuroPace UNO Q", loop=loop)
    await server.add_new_service(SERVICE)
    await server.add_new_characteristic(SERVICE, EVENTS,
        GATTCharacteristicProperties.notify | GATTCharacteristicProperties.read,
        bytearray(), GATTAttributePermissions.readable)
    await server.add_new_characteristic(SERVICE, COMMANDS,
        GATTCharacteristicProperties.write, bytearray(), GATTAttributePermissions.writable)
    server.read_request_func = lambda characteristic, **kwargs: characteristic.value

    def write_command(characteristic, value, **kwargs):
        try:
            command = json.loads(bytes(value))
            if command.get("type") == "calibrate" and command.get("phase") in ("eyes_closed", "easy", "hard", "done", "reset"):
                pipeline.calibrate(command["phase"])
        except (ValueError, TypeError):
            pass
    server.write_request_func = write_command
    pipeline.on_frame(frame_ready)
    pipeline.start()
    threading.Thread(target=lambda: App.run(user_loop=poll_button), daemon=True).start()
    await server.start()

    async def heartbeat():
        while True:
            enqueue({"type": "status", "button_ready": button_state["ready"]})
            await asyncio.sleep(2)
    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        while True:
            message = await queue.get()
            sequence += 1
            message["seq"] = sequence
            wire = (json.dumps(message, separators=(",", ":"), allow_nan=False) + "\n").encode()
            # 20-byte chunks also fit the minimum ATT MTU. Laptop reassembles lines.
            for offset in range(0, len(wire), 20):
                server.get_characteristic(EVENTS).value = bytearray(wire[offset:offset + 20])
                server.update_value(SERVICE, EVENTS)
                await asyncio.sleep(.01)
    finally:
        stopped.set()
        heartbeat_task.cancel()
        pipeline.stop()
        await server.stop()


asyncio.run(main())
