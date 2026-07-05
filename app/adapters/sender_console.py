import logging
import uuid

logger = logging.getLogger("boekvast.outbound")


class ConsoleSender:
    """Starter MessageSender: logs instead of sending. Swap for SMTP/WhatsApp
    adapters later; the FR-31 approval gate in the service layer stays the same."""

    def send(self, *, channel: str, recipient: str, subject: str, body: str) -> str:
        ref = f"console-{uuid.uuid4().hex[:10]}"
        logger.info("OUTBOUND [%s] via %s aan %s: %s — %s", ref, channel, recipient, subject, body)
        return ref
