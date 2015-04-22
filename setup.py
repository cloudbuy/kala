from distutils.core import setup

setup(
    name='kala',
    version='0.1',
    packages=[''],
    url='https://github.com/cloudbuy/kala',
    license='MIT',
    author='Paul Etherton',
    author_email='paul@pjetherton.co.uk',
    description='Simple read-only REST API for mongoDB',
    requires=[
        'bottle',
        'bottle_mongodb',
        'pymongo'
    ]
)
