from pathlib import Path

from setuptools import find_namespace_packages, setup

# Load packages from requirements.txt
BASE_DIR = Path(__file__).parent
with open(Path(BASE_DIR, "requirements.txt")) as file:
    required_packages = [ln.strip() for ln in file.readlines()]

# Define our package
setup(
    name="LearnX",
    version=0.1,
    description="Multi-LLM personalised learning platform with RAG and adaptive assessment",
    author="hqanhh",
    author_email="huynhquynhanh2003@gmail.com",
    url="https://github.com/anasraza57/LearnX",
    python_requires=">=3.10",
    packages=find_namespace_packages(),
    install_requires=[required_packages],
    extras_require={
        "dev": ["pre-commit==2.19.0"],
    },
)
