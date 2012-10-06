from setuptools import setup, find_packages
import sys, os

here = os.path.abspath(os.path.dirname(__file__))
try:
    README = open(os.path.join(here, 'README.rst')).read()
except IOError:
    README = ''

version = "0.0.1"

setup(name='gearbox',
      version=version,
      description="Command line toolkit born as a PasteScript replacement for the TurboGears2 web framework",
      long_description=README,
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Alessandro Molina',
      author_email='alessandro.molina@axant.it',
      url='https://bitbucket.org/_amol_/gearbox',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
        "cliff",
        "tempita"
      ],
      entry_points={
        'console_scripts': [
            'gearbox = gearbox.main:main'
            ],
        'gearbox.commands': [
            'makepackage = gearbox.commands.basic_package:MakePackageCommand',
            'serve = gearbox.commands.serve:ServeCommand',
            'setup-app = gearbox.commands.setup_app:SetupAppCommand'
            ],
        'paste.server_runner': [
            'wsgiref = gearbox.commands.serve:wsgiref_server_runner',
            'cherrypy = gearbox.commands.serve:cherrypy_server_runner',
            'gevent = gearbox.commands.serve:gevent_server_runner'
            ]
      })
