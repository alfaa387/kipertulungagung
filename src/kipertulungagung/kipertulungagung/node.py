"""Node utama Kiper Tulungagung.

Node ini menjadi penghubung antara:
- data jarak bola (`/vision/hasil_servo`),
- deteksi posisi bola (`/obj_detect`),
- tombol OpenCR (`/robotis/open_cr/button`),
- action module (`page_num`, `movement_done`, `status`),
- head module untuk scan dan tracking.

Logika jarak dipisahkan ke `distance_guard.py`, state machine page ke
`action_manager.py`, dan kontrol kepala ke `head_manager.py`.
"""

import time

from rclpy.node import Node
from robotis_controller_msgs.msg import StatusMsg
from std_msgs.msg import Float32, String

from .action_manager import PageActionManager
from .constants import (
    BUTTON_MODE,
    BUTTON_NAMES,
    BUTTON_START,
    BUTTON_USER,
    TOPIC_BALL_DETECTION,
    TOPIC_BALL_DISTANCE,
    TOPIC_BUTTON,
    TOPIC_ENABLE_MODULE,
    TOPIC_MOVEMENT_DONE,
    TOPIC_ROBOT_STATUS,
)
from .distance_guard import BallDistanceGuard
from .head_manager import HeadManager
from .parameters import declare_parameters, Parameters


class KiperTulungagung(Node):
    """Mengatur alur kiper dari tombol sampai perpindahan page."""

    def __init__(self):
        super().__init__('kiper_tulungagung')

        declare_parameters(self)
        self.params = Parameters(self)

        self.module_pub = self.create_publisher(
            String,
            TOPIC_ENABLE_MODULE,
            10
        )

        self.actions = PageActionManager(
            self,
            self.params,
            self.module_pub
        )
        self.head = HeadManager(
            self,
            self.params,
            self.module_pub
        )
        self.distance_guard = BallDistanceGuard(self.params)

        self.standing = False
        self.kiper_active = False
        self.current_page = None
        self.last_button_time = 0.0

        self.create_subscription(
            Float32,
            TOPIC_BALL_DISTANCE,
            self._on_distance,
            10
        )
        self.create_subscription(
            String,
            TOPIC_BALL_DETECTION,
            self._on_ball,
            10
        )
        self.create_subscription(
            String,
            TOPIC_BUTTON,
            self._on_button,
            10
        )
        self.create_subscription(
            String,
            TOPIC_MOVEMENT_DONE,
            self._on_movement_done,
            10
        )
        self.create_subscription(
            StatusMsg,
            TOPIC_ROBOT_STATUS,
            self._on_status,
            10
        )

        self._startup_timer = self.create_timer(
            0.5,
            self._startup_enable
        )
        self.create_timer(
            self.params.get_float('loop_period_sec'),
            self._on_timer
        )

        self.get_logger().info(
            'Kiper Tulungagung siap | '
            f"user: page {self.params.get_int('page_naik')}/"
            f"{self.params.get_int('page_turun')} | "
            'mode: scan | start: kiper | '
            f"jarak < {self.params.get_float('threshold_cm'):.0f} cm -> "
            f"page {self.params.get_int('page_dekat')}, "
            f"> {self.params.get_float('threshold_cm'):.0f} cm -> "
            f"page {self.params.get_int('page_jauh')}"
        )

    def _startup_enable(self):
        """Aktifkan action module sekali agar page tidak ditolak."""
        self._startup_timer.cancel()

        if not self.params.get_bool('auto_enable_action_module'):
            return

        self.head.deactivate()
        self.actions.enable_action_module()
        self.get_logger().info(
            'Action module diaktifkan saat startup'
        )

    def _on_timer(self):
        """Siklus utama node setiap `loop_period_sec`."""
        now = time.monotonic()

        self.head.process_enable(now)

        result = self.actions.tick(now)
        if result is not None:
            self._apply_page_result(result)

        self.head.update(now, self.actions.running)
        self._process_kiper(now)

    def _on_distance(self, msg):
        """Terima jarak bola terbaru."""
        self.distance_guard.update(
            float(msg.data),
            time.monotonic()
        )

    def _on_ball(self, msg):
        """Teruskan deteksi bola ke pengelola head."""
        self.head.on_ball(
            msg,
            self.actions.running,
            time.monotonic()
        )

    def _on_button(self, msg):
        """Filter tombol, lalu panggil aksi sesuai jenis tombol."""
        button = msg.data.strip().lower()

        if button not in BUTTON_NAMES:
            return

        now = time.monotonic()
        debounce = self.params.get_float('button_debounce_sec')
        if (now - self.last_button_time) < debounce:
            return

        self.last_button_time = now

        if self.actions.running:
            self.get_logger().warn(
                f'Tombol {button} diabaikan: action masih berjalan'
            )
            return

        if button == BUTTON_USER:
            self._handle_user_button()
        elif button == BUTTON_MODE:
            self._handle_mode_button()
        elif button == BUTTON_START:
            self._handle_start_button()

    def _handle_user_button(self):
        """Tombol USER: page 80 untuk berdiri, page 15 untuk turun."""
        self.current_page = None
        self.distance_guard.clear_candidate()

        if self.standing:
            self.kiper_active = False
            self.get_logger().info('USER: page 15 (turun)')
            self._request_page(self.params.get_int('page_turun'))
        else:
            self.get_logger().info('USER: page 80 (naik)')
            self._request_page(self.params.get_int('page_naik'))

    def _handle_mode_button(self):
        """Tombol MODE: nyalakan head module atau toggle scan."""
        self.head.handle_mode_button(time.monotonic())

    def _handle_start_button(self):
        """Tombol START: aktif/nonaktifkan logika jarak kiper."""
        if not self.standing:
            self.get_logger().warn(
                'START diabaikan: tekan USER untuk page 80 dulu'
            )
            return

        self.kiper_active = not self.kiper_active
        self.distance_guard.reset()

        if self.kiper_active:
            self.current_page = None
            if not self.head.active and not self.head.pending:
                self.head.request_enable()
            self.get_logger().info('START: KIPER AKTIF')
        else:
            self.get_logger().info('START: KIPER NONAKTIF')

    def _request_page(self, page):
        """Minta action manager memainkan page tertentu."""
        now = time.monotonic()

        if not self.actions.request(page, self.head.active, now):
            return False

        self.head.deactivate()
        self.distance_guard.clear_candidate()
        return True

    def _apply_page_result(self, result):
        """Terapkan hasil page ke status berdiri, page aktif, dan head."""
        page = result.page
        page_naik = self.params.get_int('page_naik')
        page_turun = self.params.get_int('page_turun')
        page_dekat = self.params.get_int('page_dekat')
        page_jauh = self.params.get_int('page_jauh')

        if page == page_naik:
            self._apply_stand_result(result)
            return

        if page == page_turun:
            self._apply_sit_result(result)
            return

        if page in (page_dekat, page_jauh):
            self._apply_kiper_page_result(result)
            return

        self.get_logger().warn(f'Page tidak dikenal: {page}')
        if result.was_head_active:
            self.head.request_enable()

    def _apply_stand_result(self, result):
        """Page 80 berhasil berarti robot siap menerima START."""
        if result.success:
            self.standing = True
            self.get_logger().info('Page 80 selesai: berdiri')
            self.head.request_enable()
            return

        self.get_logger().error('Page 80 gagal')
        self.standing = False
        if result.was_head_active:
            self.head.request_enable()

    def _apply_sit_result(self, result):
        """Page 15 menghentikan kiper dan menonaktifkan head."""
        if result.success:
            self.standing = False
            self.kiper_active = False
            self.current_page = None
            self.head.deactivate()
            self.get_logger().info('Page 15 selesai: IDLE')
            return

        self.get_logger().error('Page 15 gagal')
        if self.standing or result.was_head_active:
            self.head.request_enable()

    def _apply_kiper_page_result(self, result):
        """Catat page 150/151 dan kembalikan kontrol ke head module.

        Page 150/151 dapat berjalan berulang sehingga tidak selalu
        mengirim `movement_done`. Karena itu timeout dianggap selesai
        agar robot tidak terkunci di action module.
        """
        self.current_page = int(result.page)

        if result.timed_out:
            self.get_logger().warn(
                f'Page {result.page} timeout: dianggap selesai'
            )
        elif not result.success:
            self.get_logger().error(
                f'Page {result.page} gagal'
            )
        else:
            self.get_logger().info(
                f'Page {result.page} selesai'
            )

        if self.standing or result.was_head_active:
            self.head.request_enable()
        else:
            self.head.deactivate()

    def _process_kiper(self, now):
        """Periksa apakah jarak bola sudah memenuhi syarat ganti page."""
        if not self.kiper_active or not self.standing:
            self.distance_guard.clear_candidate()
            return

        if self.actions.running or not self.head.active:
            return

        target_page = self.distance_guard.next_request(
            now,
            self.current_page,
            self.actions.last_publish_time
        )

        if target_page is not None:
            self._request_page(target_page)

    def _on_movement_done(self, msg):
        """Terima penanda selesainya action dari action module."""
        result = self.actions.on_movement_done(msg)
        if result is not None:
            self._apply_page_result(result)

    def _on_status(self, msg):
        """Terima status error atau sukses dari action module."""
        result = self.actions.on_status(msg)
        if result is not None:
            self._apply_page_result(result)
