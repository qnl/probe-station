import setuptools, os.path

# Taken from https://packaging.python.org/guides/single-sourcing-package-version/
def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()

def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='probe-station',
    version=get_version('probe/_version.py'),
    author='Larry Chen',
    author_email='larrychen@berkeley.edu',
    description='Probe station automation',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/qnl/probe-station',
    packages=['probe'],
    package_dir={'probe': 'probe'},
    provides=['probe'],
    install_requires=['numpy', 'h5py', 'matplotlib'],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Apache 2.0',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
)