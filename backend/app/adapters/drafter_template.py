class TemplateDrafter:
    """Starter Drafter: fixed Dutch templates filled with context. Swap for an
    LLM-backed Drafter later — same interface, same approval gate."""

    version = "template-1"

    TEMPLATES = {
        "onboarding_document_request": (
            "Beste {client_name},\n\n"
            "Om uw dossier bij {org_name} in orde te brengen hebben we nog het volgende "
            "document van u nodig: {document_label}.\n\n"
            "U kan dit veilig bezorgen via ons uploadformulier of als antwoord op dit bericht.\n\n"
            "Alvast bedankt!\n{org_name}"
        ),
        "opdrachtbrief": (
            "OPDRACHTBRIEF\n\n"
            "Tussen {org_name}, hierna 'het kantoor', en {client_name}"
            "{vat_clause}, hierna 'de klant', wordt overeengekomen:\n\n"
            "1. Opdracht — Het kantoor verzorgt de boekhouding, de btw-aangiftes en de "
            "fiscale aangiftes van de klant, op basis van de door de klant aangeleverde "
            "stukken.\n"
            "2. Aanlevering — De klant bezorgt de stukken tijdig en volledig via de "
            "afgesproken kanalen.\n"
            "3. Antiwitwasverplichtingen — Het kantoor voert het wettelijk verplichte "
            "klantenonderzoek uit (identificatie, UBO, risicoprofiel) conform de "
            "antiwitwaswetgeving en de ITAA-richtlijnen.\n"
            "4. Vergoeding — Volgens de tariefafspraken in bijlage.\n"
            "5. Duur — Onbepaalde duur, opzegbaar door beide partijen met inachtneming "
            "van een redelijke termijn.\n\n"
            "Opgemaakt in tweevoud.\n\n"
            "Voor het kantoor,\t\tVoor de klant,\n{org_name}\t\t{client_name}"
        ),
        "deadline_reminder": (
            "Beste {client_name},\n\n"
            "De deadline voor {deadline_label} ({period}) nadert: {due_date}. "
            "Om dit tijdig in orde te brengen missen we nog stukken in uw dossier"
            "{missing_clause}.\n\n"
            "Kan u ons de ontbrekende stukken zo snel mogelijk bezorgen?\n\n"
            "Met vriendelijke groeten,\n{org_name}"
        ),
    }

    def draft(self, kind: str, context: dict) -> str:
        template = self.TEMPLATES.get(kind)
        if template is None:
            raise ValueError(f"Onbekend draft-type: {kind}")
        ctx = {
            "vat_clause": "",
            "missing_clause": "",
            **context,
        }
        if ctx.get("vat_number"):
            ctx["vat_clause"] = f" (BTW {ctx['vat_number']})"
        if ctx.get("missing_labels"):
            ctx["missing_clause"] = f": {', '.join(ctx['missing_labels'])}"
        return template.format(**ctx)
