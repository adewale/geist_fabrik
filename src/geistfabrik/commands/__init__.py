"""Command classes for the GeistFabrik CLI.

This package implements the Command pattern for the CLI, providing:
- BaseCommand: Shared infrastructure for all commands
- Individual command classes: InitCommand, InvokeCommand, etc.

Each command encapsulates its own logic while sharing common functionality
like vault validation, config loading, and error handling through BaseCommand.
"""

from .base import BaseCommand, CommandContext, ExecutionContext, find_vault_root
from .batch_runner import TestAllCommand
from .initialize import InitCommand
from .invoke import InvokeCommand
from .runner import TestCommand
from .stats import StatsCommand
from .validate import ValidateCommand

__all__ = [
    "BaseCommand",
    "CommandContext",
    "ExecutionContext",
    "InitCommand",
    "InvokeCommand",
    "StatsCommand",
    "TestCommand",
    "TestAllCommand",
    "ValidateCommand",
    "find_vault_root",
]
