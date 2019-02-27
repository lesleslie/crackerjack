from io import open
from os import path as op

from setuptools import setup

basedir = op.abspath(op.dirname(__file__))
version = open(op.join(basedir, "VERSION")).read().strip()

setup(
    name="CrackerJack",
    version=version,
    packages=["crackerjack"],
    test_suite="pytest",
    include_package_data=True,
    license="BSD 3-clause",
    versions=[version],
    py_modules=["crackerjack"],
    description="PEP 8000 - crackerjack code formatting style.",
    long_description=open(op.join(basedir, "README.md")).read(),
    long_description_content_type="text/markdown",
    url="https://gitlab.com/lesleslie/crackerjack",
    author="Les Leslie",
    author_email="les@wedgwoodwebworks.com",
    maintainer="Les Leslie",
    maintainer_email="les@wedgwoodwebworks.com",
    entry_points={
        "console_scripts": ["crackerjack=crackerjack.crackerjack:crackerjack"]
    },
    classifiers=[
        "Environment :: Console",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
    ],
    keywords="black",
)
