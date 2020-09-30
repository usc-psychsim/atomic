import pathlib
from setuptools import setup, find_packages

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / 'README.md').read_text(encoding='utf-8')

setup(
    name='atomic',
    version='1.0',
    license="MIT",
    description='PsychSim tools for the ATOMIC team within the ASIST program',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/usc-psychsim/atomic',
    packages=find_packages(),
    scripts=[
    ],
    install_requires=[
        'psychsim @ git+https://github.com/usc-psychsim/psychsim.git',
        'numpy',
        'jsonpickle',
        'pandas',
        'matplotlib',
        'plotly'
    ],
    extras_require={
        'ml': [
            'model-learning @ git+https://github.com/usc-psychsim/model-learning',
            'python-igraph',
            'scipy',
            'sklearn'
        ],
    },
    zip_safe=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
