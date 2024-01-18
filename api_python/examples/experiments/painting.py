#! /usr/bin/env python3

###
# KINOVA (R) KORTEX (TM)
#
# Copyright (c) 2018 Kinova inc. All rights reserved.
#
# This software may be modified and distributed
# under the terms of the BSD 3-Clause license.
#
# Refer to the LICENSE file for details.
#
###

import time
import sys
import os
import threading
from painting_utils import *

from kortex_api.autogen.client_stubs.BaseClientRpc import BaseClient
from kortex_api.autogen.client_stubs.BaseCyclicClientRpc import BaseCyclicClient
from kortex_api.autogen.client_stubs.ActuatorConfigClientRpc import ActuatorConfigClient
from kortex_api.autogen.client_stubs.ActuatorCyclicClientRpc import ActuatorCyclicClient

from kortex_api.autogen.messages import Session_pb2, Base_pb2

# Maximum allowed waiting time during actions (in seconds)
TIMEOUT_DURATION = 10

# Create closure to set an event after an END or an ABORT
def check_for_sequence_end_or_abort(e):
    """Return a closure checking for END or ABORT notifications on a sequence

    Arguments:
    e -- event to signal when the action is completed
        (will be set when an END or ABORT occurs)
    """

    def check(notification, e = e):
        event_id = notification.event_identifier
        task_id = notification.task_index
        if event_id == Base_pb2.SEQUENCE_TASK_COMPLETED:
            print("Sequence task {} completed".format(task_id))
        elif event_id == Base_pb2.SEQUENCE_ABORTED:
            print("Sequence aborted with error {}:{}"\
                .format(\
                    notification.abort_details,\
                    Base_pb2.SubErrorCodes.Name(notification.abort_details)))
            e.set()
        elif event_id == Base_pb2.SEQUENCE_COMPLETED:
            print("Sequence completed.")
            e.set()
    return check

# Create closure to set an event after an END or an ABORT
def check_for_end_or_abort(e):
    """Return a closure checking for END or ABORT notifications

    Arguments:
    e -- event to signal when the action is completed
        (will be set when an END or ABORT occurs)
    """
    def check(notification, e = e):
        print("EVENT : " + \
              Base_pb2.ActionEvent.Name(notification.action_event))
        if notification.action_event == Base_pb2.ACTION_END \
        or notification.action_event == Base_pb2.ACTION_ABORT:
            e.set()
    return check

#
# Example related functions
#
def example_move_to_home_position(base):
    # Make sure the arm is in Single Level Servoing mode
    base_servo_mode = Base_pb2.ServoingModeInformation()
    base_servo_mode.servoing_mode = Base_pb2.SINGLE_LEVEL_SERVOING
    base.SetServoingMode(base_servo_mode)
    
    # Move arm to ready position
    print("Moving the arm to a safe position")
    action_type = Base_pb2.RequestedActionType()
    action_type.action_type = Base_pb2.REACH_JOINT_ANGLES
    action_list = base.ReadAllActions(action_type)
    action_handle = None
    for action in action_list.action_list:
        if action.name == "Home":
            action_handle = action.handle

    if action_handle == None:
        print("Can't reach safe position. Exiting")
        sys.exit(0)

    e = threading.Event()
    notification_handle = base.OnNotificationActionTopic(
        check_for_end_or_abort(e),
        Base_pb2.NotificationOptions()
    )

    base.ExecuteActionFromReference(action_handle)

    # Leave time to action to complete # TODO timing out here!!
    finished = e.wait(TIMEOUT_DURATION)
    base.Unsubscribe(notification_handle)
    
    if not finished:
        print("Timeout on action notification wait")
    return finished

class GripperCommandExample:
    def __init__(self, router, proportional_gain = 2.0):

        self.proportional_gain = proportional_gain
        self.router = router

        # Create base client using TCP router
        self.base = BaseClient(self.router)

    def ExampleSendGripperCommands(self, base, position):

        # Create the GripperCommand we will send
        gripper_command = Base_pb2.GripperCommand()
        finger = gripper_command.gripper.finger.add()

        # e = threading.Event()
        # notification_handle = base.OnNotificationActionTopic(
        #     check_for_end_or_abort(e),
        #     Base_pb2.NotificationOptions()
        # )

        # Close the gripper with position increments
        print("Performing gripper test in position...")
        gripper_command.mode = Base_pb2.GRIPPER_POSITION
        finger.finger_identifier = 1
        finger.value = position
        print("Going to position {:0.2f}...".format(finger.value))
        self.base.SendGripperCommand(gripper_command)
        time.sleep(1) # necessary, gives gripper time to move
        


def angular_action(base, joint_angles):

    print("Starting angular action movement ...")
    action = Base_pb2.Action()
    action.name = "Example angular action movement"
    action.application_data = ""

    actuator_count = base.GetActuatorCount()
    
    for joint_id in range(actuator_count.count):
        joint_angle = action.reach_joint_angles.joint_angles.joint_angles.add()
        joint_angle.joint_identifier = joint_id
        joint_angle.value = joint_angles[joint_id]

    e = threading.Event()
    notification_handle = base.OnNotificationActionTopic(
        check_for_end_or_abort(e),
        Base_pb2.NotificationOptions()
    )
    
    print("Executing action")
    base.ExecuteAction(action)

    print("Waiting for movement to finish ...")
    finished = e.wait(TIMEOUT_DURATION)
    base.Unsubscribe(notification_handle)

    if finished:
        print("Angular movement completed")
    else:
        print("Timeout on action notification wait")
    return finished

def cartesian_action(base, base_cyclic, pose):

    x, y, z, theta_x, theta_y, theta_z = pose
    print("Starting Cartesian action movement ...")
    action = Base_pb2.Action()
    action.name = "Example Cartesian action movement"
    action.application_data = ""

    feedback = base_cyclic.RefreshFeedback()

    cartesian_pose = action.reach_pose.target_pose
    cartesian_pose.x = x #feedback.base.tool_pose_x          # (meters)
    cartesian_pose.y = y #feedback.base.tool_pose_y - 0.1    # (meters)
    cartesian_pose.z = z #feedback.base.tool_pose_z - 0.2    # (meters)NGLES
    cartesian_pose.theta_x = theta_x # (degrees)
    cartesian_pose.theta_y = theta_y # (degrees)
    cartesian_pose.theta_z = theta_z # (degrees)

    e = threading.Event()
    notification_handle = base.OnNotificationActionTopic(
        check_for_end_or_abort(e),
        Base_pb2.NotificationOptions()
    )

    print("Executing action")
    base.ExecuteAction(action)

    print("Waiting for movement to finish ...")
    finished = e.wait(TIMEOUT_DURATION)
    base.Unsubscribe(notification_handle)

    if finished:
        print("Cartesian movement completed")
    else:
        print("Timeout on action notification wait")
    return finished


def main():
    # Import the utilities helper module
    import argparse
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import utilities

    # Parse arguments
    parser = argparse.ArgumentParser()
    args = utilities.parseConnectionArguments()

    ROBOT_ORIGIN = (0.61, 0.195, .063, 90, 0, 90) # bottom left corner of paper
    # hover ~5cm above actual colors
    COLOR1_POS = (0.652, -0.067, 0.07, 90, 0, 90) # top left
    COLOR2_POS = (0.614, -0.067, 0.07, 90, 0, 90) # middle left
    COLOR3_POS = (0.573, -0.067, 0.07, 90, 0, 90) # bottom left
    COLOR4_POS = (0.652, -0.116, 0.07, 90, 0, 90) # top right
    COLOR5_POS = (0.614, -0.116, 0.07, 90, 0, 90) # middle right
    COLOR6_POS = (0.573, -0.116, 0.07, 90, 0, 90) # bottom right
    
    # Painting
    image_path = 'stanford_logo.png'
    save_path = 'stanford_painting.png'
    brushstrokes, colors = painting(image_path, save_path, ROBOT_ORIGIN)

    # Create connection to the device and get the router
    with utilities.DeviceConnection.createTcpConnection(args) as router:

        # Create required services
        gripper = GripperCommandExample(router)
        base = BaseClient(router)
        base_cyclic = BaseCyclicClient(router)

        success = True
        gripper_pos = 0.89 # grip the paintbrush
        gripper.ExampleSendGripperCommands(base, gripper_pos)

        # HOME
        success &= example_move_to_home_position(base)

        for stroke in brushstrokes:
            start_pos = stroke[0]
            end_pos = stroke[1]
            color = stroke[2]

            # GO TO COLOR
            if color == colors[0]:
                color_pos = COLOR1_POS
            elif color == colors[1]:
                color_pos = COLOR2_POS
                print('white, skip.')
                continue
            elif color == colors[2]:
                color_pos = COLOR3_POS
            elif color == colors[3]:
                color_pos = COLOR4_POS
            else:
                print("ERROR: color not found")
                return 1

            # GO TO COLOR
            lifted_color_pos = (color_pos[0], color_pos[1], color_pos[2] + .05, color_pos[3], color_pos[4], color_pos[5])
            success &= cartesian_action(base, base_cyclic, lifted_color_pos)

            # DIP IN COLOR
            success &= cartesian_action(base, base_cyclic, color_pos)

            # LIFT UP
            success &= cartesian_action(base, base_cyclic, lifted_color_pos)
            
            # START OF STROKE
            lifted_start_pos = (start_pos[0], start_pos[1], start_pos[2] + .05, start_pos[3], start_pos[4], start_pos[5])
            success &= cartesian_action(base, base_cyclic, lifted_start_pos)
            success &= cartesian_action(base, base_cyclic, start_pos)

            # PAINT
            lifted_end_pos = (end_pos[0], end_pos[1], end_pos[2] + .05, end_pos[3], end_pos[4], end_pos[5])
            success &= cartesian_action(base, base_cyclic, end_pos)

            # LIFT UP
            success &= cartesian_action(base, base_cyclic, lifted_end_pos)

            print(f'\nstart, end, color_pos: \n{start_pos}, \n{end_pos}, \n{color_pos}, \n{lifted_color_pos}, \n{lifted_start_pos}, \n{end_pos}')

        return 0 if success else 1

if __name__ == "__main__":
    exit(main())