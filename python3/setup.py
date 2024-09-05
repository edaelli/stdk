import sys
from setuptools import setup, find_packages, Extension


# Require at least python 3.5
if sys.version_info < (3, 5):
    raise Exception("Python >= 3.5 required!\nYou are using: {}".format(sys.version))


# Python C extensions
if sys.platform == 'linux':
    # Use HugePages for linux
    memory_ext = Extension('hugepages',
                           define_macros=[('MAJOR_VERSION', '0'),
                                          ('MINOR_VERSION', '1')],
                           include_dirs=[],
                           libraries=[
                               'hugetlbfs',
                           ],
                           extra_compile_args=[],
                           extra_link_args=[],
                           sources=['lone/system/linux/hugepages.c'])

setup(name='lone',
      version='0.1',
      description='Python Userspace Storage Device Test Framework',
      url=None,
      author='Edoardo Daelli',
      author_email='edoardo.daelli@gmail.com',
      license='MIT',
      packages=find_packages(),
      zip_safe=False,
      install_requires=[
          'setuptools',
          'wheel',
          'tox',
          'ioctl_opt',
          'pytest-cov',
          'pytest-mock',
          'pytest-runner',
          'pylama',
          'pyudev',
          'pyyaml',
      ],
      include_package_data=True,
      entry_points={
          'console_scripts': [
              'lone = scripts.lone:main',
              'lone_setup = scripts.lone_setup:main',
          ],
      },
      setup_requires=[
      ],
      tests_require=[
      ],
      ext_modules=[
          memory_ext,
      ],
      cmdclass={
      },)
