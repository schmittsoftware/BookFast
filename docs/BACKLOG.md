# Backlog / parkeerlijst

Kandidaten voor de volgende cyclus (fase 2 van `docs/WORKFLOW.md`). Nieuwe ideeën die
tijdens een bouwfase opduiken komen hier — nooit rechtstreeks de lopende slice in.

Items gemarkeerd *(herbouw)* zijn vóór de reset van juli 2026 al eens gebouwd en bewust
teruggedraaid wegens feature creep: het concept is gevalideerd, de herbouw gebeurt in
bewuste slices. De oude implementatie staat als referentie op de remote branch
`origin/development` — raadplegen mag, klakkeloos terugkopiëren niet.

## MVP-kritieke slice (CLAUDE.md §6 — bouwvolgorde aanhouden)

- [ ] **FR-01 E-mail-intake (IMAP)** — eerste echte channel-adapter achter de bestaande intake-seam
- [ ] **Echte LLM-extractor** — `DocumentExtractor`-adapter die de stub vervangt (FR-10/11/12); EU-verwerkingskeuze eerst bevestigen
- [ ] **FR-20/21 Reviewscherm afwerken** — origineel + velden, correcties <3 clicks *(herbouw, kern bestaat)*
- [ ] **FR-02 Upload-formulier** — login-vrij, per-kantoor token *(herbouw)*

## Gevalideerde concepten, na de kern

- [ ] **Client-model + sender-matching FR-06/07** — verwijderd bij "Phase 2 cleanup"; nodig vóór alles hieronder
- [ ] **Dossiers/Cases FR-40/41** — groepering per klant per periode *(herbouw)*
- [ ] **Opvolging per klant FR-30/31/32** — concepten + goedkeuringspoort + verzonden-historiek *(herbouw)*
- [ ] **Deadline-bewaking** — Belgische fiscale kalender, escalatie naar opvolgconcepten *(herbouw)*
- [ ] **Klant-trajecten** — onboarding/antiwitwas, rechtsvorm-conversie, stopzetting & faillissement, checklist-gedreven *(herbouw)*
- [ ] **Dashboard-uitbreiding** — deadlines-, opvolging- en trajectenkaarten *(herbouw; brak bij laatste poging — eerst kern stabiel)*
- [ ] **FR-42 Dossier-export (PDF)**
- [ ] **FR-50/51 Tijd-bespaard-methodologie** — pilotmetriek, nu heuristiek
- [ ] **FR-03 WhatsApp-intake** — afhankelijk van validatiegesprekken
- [ ] **Auth / sessies** — nodig vóór pilot met echte data
- [ ] **Alembic-migraties** — vóór de eerste echte klantdata

## Ideeën (nog niet gescoord)

- [ ] Uitklaringen-flow (vraaglijst onduidelijke transacties → klant antwoordt per item)
- [ ] Inbox-triage voorbij documenten (vraag-classificatie → conceptantwoord)
- [ ] Peppol-readiness-tracker per klant
- [ ] CODA/bankafschrift-statustracking per klant
