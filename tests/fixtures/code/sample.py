"""Fixture module."""


def top(x):
    return x


class Suite:
    """A class."""

    @staticmethod
    def build(n):
        return n

    def run(self):
        def inner():
            return 1

        return inner()

    class Nested:
        def run(self):
            return 2


async def fetch():
    return 3


def test_top():
    assert top(1) == 1
