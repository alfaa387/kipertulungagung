"""Launch file untuk menjalankan node Kiper Tulungagung."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Muat config YAML lalu jalankan executable `kiper`."""
    config_file = os.path.join(
        get_package_share_directory('kipertulungagung'),
        'config',
        'kiper.yaml'
    )

    return LaunchDescription([
        Node(
            package='kipertulungagung',
            executable='kiper',
            name='kiper_tulungagung',
            output='screen',
            parameters=[config_file],
        ),
    ])
