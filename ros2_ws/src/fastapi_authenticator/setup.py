from setuptools import find_packages, setup

package_name = 'fastapi_authenticator'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=[
        'setuptools',
        'uvicorn',
        'fastapi'
    ],
    zip_safe=True,
    maintainer='americo',
    maintainer_email='americo.cherubini2003@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest'
        ],
    },
    entry_points={
        'console_scripts': [
            'serve = fastapi_authenticator.auth_server:main'
        ],
    },
)