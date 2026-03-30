"""
Hello World contract — Day 1 sanity check.
Confirms Algokit toolchain can compile and deploy to testnet.
Delete after Day 1.
"""

from algopy import ARC4Contract, String
from algopy.arc4 import abimethod


class HelloWorld(ARC4Contract):
    """Minimal ARC4 contract to verify deploy pipeline works."""

    @abimethod()
    def hello(self, name: String) -> String:
        """Return a greeting string."""
        return "Hello, " + name
