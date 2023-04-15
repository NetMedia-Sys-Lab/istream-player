#!/usr/bin/env python3

from setuptools import find_packages, setup

setup(
    name="istream-player",
    version="0.3.0",
    description="IStream DASH Player",
    author="Akram Ansari",
    author_email="mdakram28@gmail.com",
    packages=find_packages(),
    entry_points={"console_scripts": ["iplay=istream_player.main:main"]},
    install_requires=[
        "wsproto",
        "aiohttp",
        "requests",
        "aioquic==0.9.20",
        "pyyaml",
        # "sslkeylog",
        "pytest",
        "parameterized",
        "matplotlib"
    ],
)
