import hashlib
from datetime import date

from app.interfaces import ExtractionResult, FieldExtraction


class StubExtractor:
    """Deterministic fake extractor so the whole pipeline (per-field confidence,
    routing, review, corrections) works end-to-end before any LLM is wired in.
    Swap for an LLM-backed DocumentExtractor without touching the services."""

    model_version = "stub-1"
    prompt_version = "v1"

    def extract(self, *, filename: str, content: bytes, sender: str) -> ExtractionResult:
        digest = hashlib.sha256(content + filename.encode()).digest()

        def conf(i: int) -> float:
            # 0.55–0.99, deterministic per document+field
            return round(0.55 + (digest[i] % 45) / 100, 2)

        lower = filename.lower()
        if lower.endswith((".jpg", ".jpeg", ".png")):
            doc_type = "bon"
        elif "factuur" in lower or lower.endswith(".pdf"):
            doc_type = "factuur"
        else:
            doc_type = "onduidelijk"

        vendor_guess = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
        amount = f"€ {digest[4] % 900 + 20},{digest[5] % 90 + 10:02d}"
        vat = f"BE 0{digest[6] % 900 + 100}.{digest[7] % 900 + 100}.{digest[8] % 900 + 100}"

        fields = [
            FieldExtraction(
                "leverancier", "Leverancier", vendor_guess.title() or "Onbekend", conf(0)
            ),
            FieldExtraction("totaalbedrag", "Totaalbedrag", amount, conf(1)),
            FieldExtraction(
                "factuurdatum", "Factuurdatum", date.today().strftime("%d-%m-%Y"), conf(2)
            ),
            FieldExtraction("btw_nummer", "BTW-nummer", vat, conf(3)),
        ]
        for f in fields:
            if f.confidence < 0.70:
                f.note = "Extractie onzeker — controleer tegen het origineel"

        return ExtractionResult(
            doc_type=doc_type,
            doc_type_confidence=conf(9),
            fields=fields,
            model_version=self.model_version,
            prompt_version=self.prompt_version,
        )
