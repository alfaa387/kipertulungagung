#!/usr/bin/env python3

"""Entry point ROS2 untuk node Kiper Tulungagung."""

import rclpy
from rclpy.executors import ExternalShutdownException

from .node import KiperTulungagung


def main(args=None):
    """Jalankan node sampai menerima SIGINT atau shutdown ROS."""
    rclpy.init(args=args)
    node = None

    try:
        node = KiperTulungagung()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # Saat Ctrl-C ganda, rclpy dapat melempar KeyboardInterrupt lagi
        # ketika node sedang dibersihkan. Cleanup dibuat best-effort.
        if node is not None:
            try:
                node.head.stop_orbit()
            except (Exception, KeyboardInterrupt):
                pass

            try:
                node.destroy_node()
            except (Exception, KeyboardInterrupt):
                pass

        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
