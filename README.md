# psyco-db

Psyco Database Library

# Configure TestPyPI
poetry config repositories.testpypi https://test.pypi.org/simple/
poetry config pypi-token.testpypi YOUR_TESTPYPI_TOKEN

When publishing, you'll use:
poetry publish -r testpypi

And for installing packages from TestPyPI:
pip install --index-url https://test.pypi.org/simple/ your-package

