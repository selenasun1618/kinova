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

#
#
# Example core functions
#

def robo_cocoa_choreo():
# POUR ANGLE, CLOCKWISE = LOWER
    pour_angle_right = 178.67

    success = True
    gripper_pos = 0.0
    gripper.ExampleSendGripperCommands(base, gripper_pos)

    # HOME
    success &= example_move_to_home_position(base)
    # START
    start_pos = (.48, -.117, .177, 90, 0, 90)
    success &= cartesian_action(base, base_cyclic, start_pos)

    # OPEN
    gripper_pos = 0.39
    gripper.ExampleSendGripperCommands(base, gripper_pos)

    # TOWARDS CUP
    pos = (.697, -.404, .23, 90, 0, 90)
    success &= cartesian_action(base, base_cyclic, pos)
    pos = (.776, -.404, .23, 90, 0, 90)
    success &= cartesian_action(base, base_cyclic, pos)

    # PICK UP CUP
    gripper_pos = 0.93
    gripper.ExampleSendGripperCommands(base, gripper_pos)
    pos = (.776, -.404, .389, 90, 0, 90)
    success &= cartesian_action(base, base_cyclic, pos)

    # POUR
    pos = (0.735, -.135, 0.389, 90, 0, 90)
    success &= cartesian_action(base, base_cyclic, pos)
    twist = [5.32, 37.76, 197.55, 259.44, 24, 53.18, 182.67]
    success &= angular_action(base, twist)

    # shake a little
    for _ in range(4):
        twist = [5.32, 37.76, 197.55, 259.44, 24, 53.18, 184.67]
        success &= angular_action(base, twist)
        twist = [5.32, 37.76, 197.55, 259.44, 24, 53.18, 182.67]
        success &= angular_action(base, twist)
    
    time.sleep(2)
    twist = [5.32, 37.76, 197.55, 259.44, 24, 53.18, 77]
    success &= angular_action(base, twist)
    
    # RETURN CUP
    pos = (.776, -.404, .389, 90, 0, 90)
    success &= cartesian_action(base, base_cyclic, pos)
    pos = (.729, -.404, .22, 90, 0, 90)
    success &= cartesian_action(base, base_cyclic, pos)
    gripper_pos = 0.39
    gripper.ExampleSendGripperCommands(base, gripper_pos)
    pos = (.6, -.404, .22, 90, 0, 90)
    success &= cartesian_action(base, base_cyclic, pos)

    # HOME
    success &= example_move_to_home_position(base)
    gripper_pos = 0.0
    gripper.ExampleSendGripperCommands(base, gripper_pos)
    
    # PICK UP STIRRER
    pos = (.79, .05, .26, 90, 0, 90)
    success &= cartesian_action(base, base_cyclic, pos)
    gripper_pos = 1.0
    gripper.ExampleSendGripperCommands(base, gripper_pos)
    # up
    pos = (.79, .05, .42, 90, 0, 90)
    success &= cartesian_action(base, base_cyclic, pos)
    # on top of cocoa
    pos = (.72, -.11, .42, 90, 0, 90)
    success &= cartesian_action(base, base_cyclic, pos)
    # down
    pos = (.72, -.155, .312, 90, 0, 90)
    success &= cartesian_action(base, base_cyclic, pos)

    # STIR
    for _ in range(7):
        pos = (.751, -.13, .312, 90, 0, 90)
        success &= cartesian_action(base, base_cyclic, pos)
        pos = (.775, -.165, .312, 90, 0, 90)
        success &= cartesian_action(base, base_cyclic, pos)
        pos = (.751, -.19, .312, 90, 0, 90)
        success &= cartesian_action(base, base_cyclic, pos)
        pos = (.72, -.155, .312, 90, 0, 90)
        success &= cartesian_action(base, base_cyclic, pos)

    # lift up
    pos = (.716, -.11, .42, 90, 0, 90)
    success &= cartesian_action(base, base_cyclic, pos)
    pos = (.616, -.11, .42, 90, 0, 90)
    success &= cartesian_action(base, base_cyclic, pos)
    # drop
    gripper_pos = 0.0
    gripper.ExampleSendGripperCommands(base, gripper_pos)

def main():
    # Import the utilities helper module
    import argparse
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import utilities

    # Parse arguments
    parser = argparse.ArgumentParser()
    args = utilities.parseConnectionArguments()

    # Create connection to the device and get the router
    with utilities.DeviceConnection.createTcpConnection(args) as router:

        # Create required services
        gripper = GripperCommandExample(router)
        base = BaseClient(router)
        base_cyclic = BaseCyclicClient(router)

        # robo_cocoa_choreo()
        success = True
        gripper_pos = 0.88 # hold a pencil
        gripper.ExampleSendGripperCommands(base, gripper_pos)

        # HOME
        success &= example_move_to_home_position(base)
        # START
        pos = (.53, .169, 0.041, 90, 0, 90)
        success &= cartesian_action(base, base_cyclic, pos)
        pos = (.55, .169, 0.041, 90, 0, 90)
        success &= cartesian_action(base, base_cyclic, pos)
        pos = (.55, .149, 0.041, 90, 0, 90)
        success &= cartesian_action(base, base_cyclic, pos)
        pos = (.53, .149, 0.041, 90, 0, 90)
        success &= cartesian_action(base, base_cyclic, pos)

        pos = (.53, .169, 0.041, 90, 0, 90)
        success &= cartesian_action(base, base_cyclic, pos)

        return 0 if success else 1

if __name__ == "__main__":
    exit(main())