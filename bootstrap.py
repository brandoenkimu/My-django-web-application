# bootstrap.py
import subprocess
import sys
import os


def run_command(cmd):
    """Run a shell command"""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    print(f"Success: {result.stdout}")
    return True


def main():
    print("Setting up Django project...")

    # 1. Check Python
    print("\n1. Checking Python installation...")
    if not run_command("python --version"):
        print("Python not found. Please install Python 3.8+")
        return

    # 2. Install pip if needed
    print("\n2. Checking pip...")
    if not run_command("python -m pip --version"):
        print("Installing pip...")
        run_command("python -m ensurepip --upgrade")

    # 3. Install basic packages
    print("\n3. Installing basic packages...")
    packages = [
        "django==5.2.8",
        "requests==2.32.5",
        "stripe==14.1.0",
        "cryptography==42.0.8",
    ]

    for package in packages:
        if not run_command(f"python -m pip install {package}"):
            print(f"Failed to install {package}")

    print("\nSetup complete!")
    print("\nTo run your project:")
    print("1. python manage.py migrate")
    print("2. python manage.py createsuperuser")
    print("3. python manage.py runserver")


if __name__ == "__main__":
    main()