from setuptools import setup, find_packages


setup(
    name = 'wsgi_intercept',
    version = '0.6.0',
    author = 'Concordus Applications, Titus Brown, Kumar McMillan, Chris Dent',
    author_email = 'cdent@peermore.com',
    license = 'MIT License',
    packages = find_packages(),
    install_requires=['httplib2']
)
