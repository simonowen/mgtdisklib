import os
from setuptools import setup

def read(filename):
    return open(os.path.join(os.path.dirname(__file__), filename), encoding='utf-8').read()

setup(name='mgtdisklib',
      version='0.5.3',
      author='Simon Owen',
      author_email='simon@simonowen.com',
      description='Disk manipulation for SAM Coupé and MGT +D disks images',
      long_description=read('ReadMe.md'),
      long_description_content_type = 'text/markdown',
      license='MIT',
      keywords='mgt disk sam coupe',
      url='https://github.com/simonowen/mgtdisklib',
      packages=['mgtdisklib', 'tests'],
      install_requires=['bitarray'],
      classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: System :: Emulators",
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: MIT License",
    ],
)
