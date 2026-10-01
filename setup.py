from setuptools import setup, find_packages

setup(
    name="flask-auth",
    version="0.1.0",
    description="Unified Session and Token Authentication for Flask",
    author="DanielKEdozie",
    packages=find_packages(),
    install_requires=[
        "Flask",
        "Flask-Login",
        "Flask-HTTPAuth",
        "PyJWT",
        "werkzeug"
    ],
    python_requires=">=3.8",
)
