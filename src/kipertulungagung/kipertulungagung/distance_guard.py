"""Pengolah jarak bola dan penjaga perpindahan page 150/151.

Modul ini hanya mengurus data jarak: filter, hysteresis, waktu stabil,
timeout data, dan jeda minimum antar-page. Modul ini tidak mengetahui
module action maupun head, sehingga mudah diuji secara terpisah.
"""

import math

from GoNasional.ema_filter import DataFilter


class BallDistanceGuard:
    """Menentukan kapan jarak bola layak memicu pergantian page."""

    def __init__(self, params):
        self._params = params
        self._distance_filter = self._new_filter()
        self._last_distance = None
        self._last_rx_time = 0.0
        self._candidate_page = None
        self._candidate_since = 0.0

    def _new_filter(self):
        return DataFilter(
            window_size=self._params.get_int('distance_filter_window'),
            alpha=self._params.get_float('distance_filter_alpha')
        )

    @property
    def last_distance(self):
        """Jarak terakhir setelah filter, atau None jika belum ada."""
        return self._last_distance

    def update(self, distance, now):
        """Terima jarak mentah dan simpan hasil filternya.

        Nilai nol, negatif, atau bukan angka dianggap data hilang. Filter
        direset agar pembacaan lama tidak tercampur dengan data baru.
        """
        if not math.isfinite(distance) or distance <= 0.0:
            self.reset()
            return

        self._last_distance = self._distance_filter.update(distance)
        self._last_rx_time = now

    def reset(self):
        """Kosongkan filter dan seluruh kandidat page."""
        self._distance_filter = self._new_filter()
        self._last_distance = None
        self._last_rx_time = 0.0
        self.clear_candidate()

    def clear_candidate(self):
        """Batalkan kandidat page yang sedang menunggu waktu stabil."""
        self._candidate_page = None
        self._candidate_since = 0.0

    def target_page(self, current_page):
        """Pilih page berdasarkan jarak dan hysteresis.

        Jika robot sudah berada di page dekat, page jauh hanya dipilih
        ketika jarak melewati batas atas (threshold + hysteresis). Jika
        robot sudah berada di page jauh, page dekat hanya dipilih ketika
        jarak turun di bawah batas bawah (threshold - hysteresis).
        """
        near_page = self._params.get_int('page_dekat')
        far_page = self._params.get_int('page_jauh')
        threshold = self._params.get_float('threshold_cm')
        hysteresis = abs(self._params.get_float('hysteresis_cm'))

        if current_page == near_page:
            if self._last_distance > threshold + hysteresis:
                return far_page
            return near_page

        if current_page == far_page:
            if self._last_distance < threshold - hysteresis:
                return near_page
            return far_page

        if self._last_distance < threshold:
            return near_page

        return far_page

    def next_request(self, now, current_page, last_publish_time):
        """Kembalikan page yang siap dikirim, atau None.

        Syarat page dikirim:
        - data jarak masih segar,
        - target berbeda dari page aktif,
        - target bertahan selama `stable_time_sec`,
        - sudah melewati `min_switch_interval_sec` dari page terakhir.
        """
        if self._last_distance is None:
            self.clear_candidate()
            return None

        data_timeout = self._params.get_float('data_timeout_sec')
        if (now - self._last_rx_time) > data_timeout:
            self.clear_candidate()
            return None

        target_page = self.target_page(current_page)

        if target_page == current_page:
            self.clear_candidate()
            return None

        if target_page != self._candidate_page:
            self._candidate_page = target_page
            self._candidate_since = now
            return None

        stable_time = self._params.get_float('stable_time_sec')
        if (now - self._candidate_since) < stable_time:
            return None

        min_interval = self._params.get_float('min_switch_interval_sec')
        if (
            last_publish_time > 0.0
            and (now - last_publish_time) < min_interval
        ):
            return None

        return target_page
