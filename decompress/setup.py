from setuptools import setup, find_packages

setup(
    name="decompress",
    version="2.0.3",
    author="Marcus LaFerrera (@mlaferrera)",
    url="https://github.com/PUNCH-Cyber/stoq-plugins-public",
    license="Apache License 2.0",
    description="Extract content from a multitude of archive formats",
    packages=find_packages(),
    include_package_data=True,
)
