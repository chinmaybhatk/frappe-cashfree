# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('requirements.txt') as f:
    install_requires = f.read().strip().split('\n')

# Get version from __version__ variable in cashfree/__init__.py
from cashfree import __version__ as version

setup(
    name='cashfree',
    version=version,
    description='Cashfree Payment Gateway Integration for Frappe',
    author='Your Company',
    author_email='your.email@example.com',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires
)