import pytest


# Evaluator unit tests have no DB dependency — override the autouse fixture
# from the parent conftest so it doesn't attempt a DB connection.
@pytest.fixture(scope="module", autouse=True)
def override_db():
    yield
