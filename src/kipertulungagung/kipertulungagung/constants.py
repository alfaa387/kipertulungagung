"""Konstanta nama topik, module, tombol, dan status robot.

Semua string protokol robot dikumpulkan di sini supaya mudah dicari dan
tidak tersebar sebagai "magic string" di dalam node.
"""

TOPIC_BALL_DISTANCE = '/vision/hasil_servo'
TOPIC_BALL_DETECTION = '/obj_detect'
TOPIC_BUTTON = '/robotis/open_cr/button'
TOPIC_MOVEMENT_DONE = '/robotis/movement_done'
TOPIC_ROBOT_STATUS = '/robotis/status'
TOPIC_ENABLE_MODULE = '/robotis/enable_ctrl_module'
TOPIC_ACTION_PAGE = '/robotis/action/page_num'

MODULE_ACTION = 'action_module'
MODULE_HEAD = 'head_control_module'

BUTTON_USER = 'user'
BUTTON_MODE = 'mode'
BUTTON_START = 'start'
BUTTON_NAMES = frozenset((BUTTON_USER, BUTTON_MODE, BUTTON_START))

HEAD_MODE_SCAN = 'scan'
HEAD_MODE_TRACK = 'track'
HEAD_MODE_HOLD = 'hold'

MOVEMENT_DONE_OK = 'action'
MOVEMENT_DONE_FAILED = 'action_failed'

STATUS_SUCCEED_PREFIX = 'Succeed to start page '
STATUS_FAILED_PREFIX = 'Failed to start page '
STATUS_CANNOT_PLAY = 'Can not play page '
STATUS_ACTION_NOT_ENABLED = 'Action Module is not enabled'
STATUS_ACTION_DISABLED = 'Action Module is disabled'
