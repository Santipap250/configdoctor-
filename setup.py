#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OBIXConfig Doctor — FPV Drone Configuration Analyzer
Setup & installation configuration
"""

from setuptools import setup, find_packages

with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='configdoctor',
    version='5.2.0',
    description='FPV Drone Configuration Analyzer & Optimization Tool',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='SanTiPapHacker',
    author_email='',
    url='https://github.com/Santipap250/configdoctor-',
    license='MIT',
    packages=find_packages(),
    python_requires='>=3.8',
    install_requires=[
        'Flask>=3.0.0',
        'gunicorn>=22.0.0',
        'Werkzeug>=3.0.0',
        'python-dotenv>=1.0.0',
        'Flask-WTF>=1.2.0',
        'Flask-Limiter>=3.5.0',
        'limits[redis]>=3.6.0',
        'Flask-Compress>=1.14',
        'numpy>=1.24.0',
        'pandas>=2.0.0',
        'Pillow>=10.0.0',
    ],
    extras_require={
        'dev': [
            'pytest>=7.4.0',
            'pytest-cov>=4.1.0',
            'pytest-flask>=1.2.0',
            'black>=23.7.0',
            'flake8>=6.0.0',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Flask',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: Thai',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Internet :: WWW/HTTP',
    ],
    keywords='fpv drone config pid tuning analyzer',
)
