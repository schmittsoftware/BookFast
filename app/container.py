from dataclasses import dataclass

from app.adapters.drafter_template import TemplateDrafter
from app.adapters.extractor_stub import StubExtractor
from app.adapters.runner_inline import InlineRunner
from app.adapters.sender_console import ConsoleSender
from app.adapters.storage_local import LocalDiskStorage
from app.config import Settings
from app.interfaces import DocumentExtractor, Drafter, FileStorage, MessageSender, TaskRunner


@dataclass
class Deps:
    """The injected dependency set handed to services. Tests and future
    deployments construct this with different adapters."""

    settings: Settings
    storage: FileStorage
    extractor: DocumentExtractor
    sender: MessageSender
    runner: TaskRunner
    drafter: Drafter


def build_deps(settings: Settings) -> Deps:
    return Deps(
        settings=settings,
        storage=LocalDiskStorage(settings.storage_dir),
        extractor=StubExtractor(),
        sender=ConsoleSender(),
        runner=InlineRunner(),
        drafter=TemplateDrafter(),
    )
