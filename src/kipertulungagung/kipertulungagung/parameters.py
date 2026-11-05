"""Deklarasi dan pembacaan parameter node Kiper Tulungagung.

Nilai default dikelompokkan berdasarkan fungsinya agar konfigurasi mudah
dibaca. Pembacaan parameter dilakukan saat dibutuhkan sehingga perubahan
parameter tetap mengikuti nilai terbaru dari ROS.
"""

PARAMETER_DEFAULTS = {
    # Jarak bola dan proteksi perpindahan page.
    'threshold_cm': 100.0,
    'hysteresis_cm': 5.0,
    'stable_time_sec': 0.5,
    'min_switch_interval_sec': 1.0,
    'data_timeout_sec': 0.5,

    # Waktu tunggu perpindahan module dan penyelesaian action.
    'module_switch_delay_sec': 0.4,
    'action_done_timeout_sec': 3.0,
    'page_retry_max': 1,

    # Tombol dan pelacakan bola.
    'button_debounce_sec': 0.3,
    'ball_timeout_sec': 0.5,

    # Nomor halaman action robot.
    'page_dekat': 150,
    'page_jauh': 151,
    'page_naik': 80,
    'page_turun': 15,

    # Timer utama dan filter jarak.
    'loop_period_sec': 0.05,
    'distance_filter_window': 5,
    'distance_filter_alpha': 0.2,

    # Module action diaktifkan sekali saat node mulai.
    'auto_enable_action_module': True,
}


def declare_parameters(node):
    """Daftarkan semua parameter node dengan nilai default."""
    for name, default in PARAMETER_DEFAULTS.items():
        node.declare_parameter(name, default)


class Parameters:
    """Pembaca parameter dengan tipe data yang sudah dikonversi."""

    def __init__(self, node):
        self._node = node

    def get_float(self, name):
        """Ambil parameter sebagai float."""
        return float(self._node.get_parameter(name).value)

    def get_int(self, name):
        """Ambil parameter sebagai integer."""
        return int(self._node.get_parameter(name).value)

    def get_bool(self, name):
        """Ambil parameter sebagai boolean."""
        return bool(self._node.get_parameter(name).value)
