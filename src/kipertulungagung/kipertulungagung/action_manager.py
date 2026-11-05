"""State machine untuk memainkan halaman action robot.

Alur singkat:
1. Minta action module aktif.
2. Tunggu module siap.
3. Kirim nomor page.
4. Tunggu `movement_done` atau timeout.
5. Kembalikan hasil page ke node untuk menentukan langkah berikutnya.

Modul ini tidak mengatur posisi berdiri, page aktif, atau head module.
Semua keputusan tingkat tinggi tersebut dilakukan oleh node.
"""

from dataclasses import dataclass
from enum import auto, Enum
import time

from std_msgs.msg import Int32, String

from .constants import (
    MODULE_ACTION,
    MOVEMENT_DONE_FAILED,
    MOVEMENT_DONE_OK,
    STATUS_ACTION_DISABLED,
    STATUS_ACTION_NOT_ENABLED,
    STATUS_CANNOT_PLAY,
    STATUS_FAILED_PREFIX,
    STATUS_SUCCEED_PREFIX,
    TOPIC_ACTION_PAGE,
)


class ActionPhase(Enum):
    """Fase eksekusi page yang sedang berjalan."""

    IDLE = auto()
    WAIT_MODULE = auto()
    WAIT_DONE = auto()


@dataclass
class PageResult:
    """Hasil akhir satu permintaan page."""

    page: int
    success: bool
    timed_out: bool = False
    was_head_active: bool = False
    reason: str = ''


class PageActionManager:
    """Mengatur pengiriman page dan perpindahan module action."""

    def __init__(self, node, params, module_pub):
        self._node = node
        self._params = params
        self._module_pub = module_pub
        self._page_pub = node.create_publisher(
            Int32,
            TOPIC_ACTION_PAGE,
            10
        )

        self._phase = ActionPhase.IDLE
        self._pending_page = None
        self._deadline = 0.0
        self._retry_count = 0
        self._was_head_active = False
        self._last_publish_time = 0.0

    @property
    def running(self):
        """Return True jika masih ada page yang sedang diproses."""
        return self._phase is not ActionPhase.IDLE

    @property
    def last_publish_time(self):
        """Waktu pengiriman page terakhir, untuk cooldown jarak."""
        return self._last_publish_time

    def enable_action_module(self):
        """Kirim permintaan agar controller memakai action module."""
        msg = String()
        msg.data = MODULE_ACTION
        self._module_pub.publish(msg)

    def request(self, page, was_head_active, now=None):
        """Mulai permintaan page baru.

        `was_head_active` disimpan agar node tahu apakah head module perlu
        diaktifkan kembali ketika page gagal.
        """
        if self.running:
            self._node.get_logger().warn(
                f'Page {page} ditolak: action masih berjalan'
            )
            return False

        if now is None:
            now = time.monotonic()

        self._was_head_active = bool(was_head_active)
        self._pending_page = int(page)
        self._retry_count = 0
        self._phase = ActionPhase.WAIT_MODULE
        self._deadline = (
            now + self._params.get_float('module_switch_delay_sec')
        )
        self.enable_action_module()

        self._node.get_logger().info(f'Request page {page}')
        return True

    def tick(self, now):
        """Proses state machine secara periodik.

        Mengembalikan `PageResult` hanya ketika page selesai atau timeout.
        """
        if self._phase is ActionPhase.WAIT_MODULE:
            if now < self._deadline:
                return None

            self._phase = ActionPhase.WAIT_DONE
            self._deadline = (
                now + self._params.get_float('action_done_timeout_sec')
            )
            self._publish_page()
            return None

        if (
            self._phase is ActionPhase.WAIT_DONE
            and now >= self._deadline
        ):
            self._node.get_logger().warn(
                f'Page {self._pending_page} timeout'
            )
            return self._finish(
                False,
                timed_out=True,
                reason='timeout'
            )

        return None

    def _publish_page(self):
        """Kirim nomor page setelah action module dianggap siap."""
        msg = Int32()
        msg.data = int(self._pending_page)
        self._page_pub.publish(msg)

        self._last_publish_time = time.monotonic()
        self._node.get_logger().info(
            f'Kirim page {self._pending_page}'
        )

    def on_movement_done(self, msg):
        """Terima hasil akhir dari action module."""
        if self._phase is not ActionPhase.WAIT_DONE:
            return None

        result = msg.data.strip().lower()
        if result == MOVEMENT_DONE_OK:
            return self._finish(True)
        if result == MOVEMENT_DONE_FAILED:
            return self._finish(
                False,
                reason=MOVEMENT_DONE_FAILED
            )
        return None

    def on_status(self, msg):
        """Terima status action module.

        Status "Action Module is not enabled" dicoba ulang beberapa kali.
        Status gagal lain langsung diselesaikan sebagai kegagalan.
        """
        if self._phase is not ActionPhase.WAIT_DONE:
            return None

        text = msg.status_msg
        page = self._pending_page

        if (
            page is not None
            and f'{STATUS_SUCCEED_PREFIX}{page}' in text
        ):
            self._node.get_logger().info(text)
            return None

        if (
            STATUS_ACTION_NOT_ENABLED in text
            or STATUS_ACTION_DISABLED in text
        ):
            return self._retry_or_finish(text)

        if page is not None and (
            f'{STATUS_FAILED_PREFIX}{page}' in text
            or f'{STATUS_CANNOT_PLAY}{page}' in text
        ):
            self._node.get_logger().error(text)
            return self._finish(False, reason=text)

        return None

    def _retry_or_finish(self, reason):
        """Ulangi page setelah module error, atau selesaikan gagal."""
        page = self._pending_page
        max_retries = self._params.get_int('page_retry_max')

        if page is None or self._retry_count >= max_retries:
            self._node.get_logger().error(reason)
            return self._finish(False, reason=reason)

        self._retry_count += 1
        self._node.get_logger().warn(
            f'{reason}; ulangi page {page} '
            f'({self._retry_count}/{max_retries})'
        )

        self._phase = ActionPhase.WAIT_MODULE
        self._deadline = (
            time.monotonic()
            + self._params.get_float('module_switch_delay_sec')
        )
        self.enable_action_module()
        return None

    def _finish(self, success, timed_out=False, reason=''):
        """Bentuk hasil akhir dan kembalikan state ke IDLE."""
        page = (
            int(self._pending_page)
            if self._pending_page is not None
            else -1
        )
        result = PageResult(
            page=page,
            success=success,
            timed_out=timed_out,
            was_head_active=self._was_head_active,
            reason=reason,
        )

        self._phase = ActionPhase.IDLE
        self._pending_page = None
        self._retry_count = 0
        self._was_head_active = False
        return result
