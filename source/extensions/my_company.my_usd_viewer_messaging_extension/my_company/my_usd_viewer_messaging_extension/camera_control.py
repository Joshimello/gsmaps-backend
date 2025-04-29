import asyncio
from pxr import Gf, UsdGeom, Usd

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
from scipy.spatial.transform import Rotation

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
            euler_angles = payload['rotation']  # e.g., [0.0, 0.0, 0.0]

            euler_angles = np.radians(euler_angles)

            C2W = np.eye(4)
            C2W[:3, :3] = Rotation.from_euler('xyz', euler_angles).as_matrix()
            C2W[:3, 3] = position

            W2C = np.linalg.inv(C2W)

            ISAAC_SIM_TO_GS_CONVENTION = np.array([
                [1,  0,  0, 0],
                [0, -1,  0, 0],
                [0,  0, -1, 0],
                [0,  0,  0, 1]
            ])
            W2C = ISAAC_SIM_TO_GS_CONVENTION @ W2C

            R = W2C[:3, :3].T
            T = W2C[:3, 3]

            rotation = Rotation.from_matrix(R).as_euler('yxz', degrees=True)

            rotation = [math.degrees(angle) for angle in rotation]

            ctx = omni.usd.get_context()
            stage = ctx.get_stage()
            camera_path = get_active_viewport_camera_string()
            camera_prim = stage.GetPrimAtPath(camera_path)

            if camera_prim:
                with Usd.EditContext(stage, Usd.EditTarget(stage.GetSessionLayer())):
                    translate_attr = camera_prim.GetAttribute('xformOp:translate')
                    if translate_attr:
                        translate_attr.Set(tuple(position))

                    rotate_attr = camera_prim.GetAttribute('xformOp:rotateYXZ')
                    if rotate_attr:
                        rotate_attr.Set(tuple([rotation[0], -rotation[1], 0]))  # [y_rot, x_rot, z_rot]
                print(f"Teleported camera to position {position} and looking at target with rotation YXZ {rotation}")



    def on_shutdown(self):
        """Clean up subscriptions"""
        self._subscriptions.clear()
