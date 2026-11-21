from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'hardware_mng'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),

        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),

        # (optional) config files
        (os.path.join('share', package_name, 'config'),
            glob('config/*') + [
                'hardware_mng/builtin_plugins/hw_configs.yaml',
            ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='americo',
    maintainer_email='americo.cherubini2003@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'hardware_mng = hardware_mng.entrypoint:main',
            'mock_client = hardware_mng.mock_client.client_node:main'
        ],
    },
)
