 
from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='gatherup',
    version='0.0.2',
    author="Neil Stoker",
    author_email="nstoker001@gmail.com",
    description='Helps you post essential Python config details to GitHub or Discourse, all beautifully formatted',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nmstoker/gatherup",
    install_requires = [
        "click>7.0,<8.0",
        "questionary>1.5,<2.0",
        "rich>3.3,<4.0",
        "confuse>1.2,<1.4",
        "importlib_resources ; python_version<'3.7'"
    ],
    extras_require = {
        "dev": [
            "pytest>3.7",
        ],
    },
    py_modules=["gatherup"],
    packages=find_packages("."),
    include_package_data=True,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development",
    ],
    )
