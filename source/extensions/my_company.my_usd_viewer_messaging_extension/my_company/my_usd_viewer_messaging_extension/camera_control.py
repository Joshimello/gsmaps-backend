import asyncio
from pxr import Gf, UsdGeom, Usd, Sdf

import carb
import carb.events
import omni.kit.app
import omni.usd
import omni.kit.livestream.messaging as messaging
from omni.kit.viewport.utility import get_active_viewport_camera_string
import math
import numpy as np
import omni.kit.pipapi
omni.kit.pipapi.install("scipy", module="scipy")
from scipy.spatial.transform import Rotation as R

class CameraManager:
    """Manages camera position and rotation"""
    def __init__(self):
        self._subscriptions = []

        # -- register outgoing events/messages
        outgoing = [
            "teleportCameraResponse",  # response to teleportCameraRequest
        ]

        for o in outgoing:
            messaging.register_event_type_to_send(o)

        # -- register incoming events/messages
        incoming = {
            'teleportCameraRequest': self._on_teleport_camera,
        }

        for event_type, handler in incoming.items():
            self._subscriptions.append(
                omni.kit.app.get_app().get_message_bus_event_stream().
                create_subscription_to_pop(handler, name=event_type)
            )

    def _on_teleport_camera(self, event: carb.events.IEvent) -> None:
        if event.type == carb.events.type_from_string("teleportCameraRequest"):
            payload = event.payload
            position = payload['position']  # e.g., [0.0, 0.0, 10.0]
            quaternion = payload['quaternion']
            euler_angles = R.from_quat(quaternion).as_euler('xyz', degrees=True)

            ctx = omni.usd.get_context()
            stage = ctx.get_stage()
            camera_path = get_active_viewport_camera_string()

            if stage is None:
                return

            camera_prim = stage.GetPrimAtPath(camera_path)

            if camera_prim:
                with Usd.EditContext(stage, Usd.EditTarget(stage.GetSessionLayer())):
                    translate_attr = camera_prim.GetAttribute('xformOp:translate')
                    translate_attr.Set(tuple(position))

                    rotate_attr = camera_prim.GetAttribute('xformOp:rotateXYZ')
                    if not rotate_attr:
                        rotate_attr = camera_prim.CreateAttribute('xformOp:rotateXYZ', Sdf.ValueTypeNames.Float3)
                    rotate_attr.Set(tuple(euler_angles))

                    xformOpOrder_attr = camera_prim.GetAttribute('xformOpOrder')
                    # Note that rotateYXZ is used in the USD viewer template
                    xformOpOrder_attr.Set(['xformOp:translate', 'xformOp:rotateXYZ', 'xformOp:scale'])

                    print(f"position: {position}, rotation: {euler_angles}")


    def on_shutdown(self):
        """Clean up subscriptions"""
        self._subscriptions.clear()
