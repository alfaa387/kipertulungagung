"""Pengelola head module untuk scan, tracking bola, dan hold.

OP3 hanya mengizinkan satu control module aktif. Saat action page berjalan,
head module harus nonaktif. Setelah page selesai, modul ini meminta head
module kembali aktif dan melanjutkan mode scan atau tracking.
"""

import time

from GoNasional.main_head_control import HeadControl
from std_msgs.msg import String

from .constants import (
    HEAD_MODE_HOLD,
    HEAD_MODE_SCAN,
    HEAD_MODE_TRACK,
    MODULE_HEAD,
)


class HeadManager:
    """Membungkus HeadControl milik GoNasional."""

    def __init__(self, node, params, module_pub):
        self._node = node
        self._params = params
        self._module_pub = module_pub

        self.head = HeadControl(node)
        self.active = False
        self.pending = False
        self.ready_at = 0.0
        self.scan_enabled = True
        self.last_ball_time = 0.0

    def deactivate(self):
        """Tandai head module nonaktif tanpa mengirim pesan module."""
        self.head.head_enabled = False
        self.active = False
        self.pending = False

    def request_enable(self, now=None):
        """Minta controller mengaktifkan head module.

        Head baru dianggap siap setelah `module_switch_delay_sec` agar
        perintah servo tidak dikirim saat module masih berpindah.
        """
        if self.active or self.pending:
            return

        if now is None:
            now = time.monotonic()

        msg = String()
        msg.data = MODULE_HEAD
        self._module_pub.publish(msg)

        self.head.head_enabled = False
        self.active = False
        self.pending = True
        self.ready_at = (
            now + self._params.get_float('module_switch_delay_sec')
        )

    def process_enable(self, now):
        """Aktifkan head setelah waktu tunggu module selesai."""
        if not self.pending or now < self.ready_at:
            return

        self.pending = False
        self.head.head_enabled = True
        self.active = True

        if self.ball_recent(now):
            self.head._enter_track_mode()
        elif self.scan_enabled:
            self.head._enter_scan_mode()
        else:
            self.head.head_mode = HEAD_MODE_HOLD

        self._node.get_logger().info('Head module aktif')

    def ball_recent(self, now):
        """Return True jika bola terdeteksi dalam `ball_timeout_sec`."""
        timeout = self._params.get_float('ball_timeout_sec')
        return (
            self.last_ball_time > 0.0
            and (now - self.last_ball_time) <= timeout
        )

    def on_ball(self, msg, action_running, now=None):
        """Proses deteksi bola dari `/obj_detect`."""
        if now is None:
            now = time.monotonic()

        if not self.active or action_running:
            return

        if not self.head.on_detection(msg):
            return

        self.last_ball_time = now

        if self.head.orbit_running:
            self.head._stop_orbit()

        if self.head.head_mode != HEAD_MODE_TRACK:
            self.head._enter_track_mode()

    def update(self, now, action_running):
        """Pilih perilaku head: tracking, scan, atau hold."""
        if not self.active or action_running or self.pending:
            return

        if self.ball_recent(now):
            if self.head.head_mode != HEAD_MODE_TRACK:
                self.head._enter_track_mode()
            self.head._track_head()
            return

        if self.scan_enabled:
            if self.head.head_mode != HEAD_MODE_SCAN:
                self.head._enter_scan_mode()
            else:
                self.head._scan_head()
        elif self.head.head_mode != HEAD_MODE_HOLD:
            self.head.head_mode = HEAD_MODE_HOLD
            self.head._publish_servo(self.head.pan, self.head.tilt)

    def handle_mode_button(self, now=None):
        """Toggle scan, atau aktifkan head module jika masih nonaktif."""
        if now is None:
            now = time.monotonic()

        if not self.active and not self.pending:
            self.scan_enabled = True
            self._node.get_logger().info(
                'MODE: aktifkan head module'
            )
            self.request_enable(now)
            return

        self.scan_enabled = not self.scan_enabled
        state = 'ON' if self.scan_enabled else 'OFF'
        self._node.get_logger().info(f'MODE: scan {state}')

        if (
            self.active
            and not self.scan_enabled
            and self.head.head_mode == HEAD_MODE_SCAN
        ):
            self.head.head_mode = HEAD_MODE_HOLD
            self.head._publish_servo(
                self.head.pan,
                self.head.tilt
            )

    def stop_orbit(self):
        """Hentikan pola orbit saat node akan berhenti."""
        self.head._stop_orbit()
