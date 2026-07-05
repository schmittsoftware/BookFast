# SE Lifecycle — Fase 1: Requirements-inzicht & Storyboards
### AI-diensten voor Boekhoudkantoren — MVP/Pilot

**Versie:** 0.1
**Doel van dit document:** requirements consolideren tot een gedeeld beeld vóór design/build, en de kernscenario's concreet maken via storyboards, als basis voor de system flow- en architectuurdiagrammen (zie `02-diagrammen.md`).

---

## 1. Requirements-inzicht

### 1.1 Kernprincipe achter alles

Dit systeem automatiseert niet de boekhouding zelf, maar de laag eromheen: intake, classificatie, review, opvolging en dossiervorming. Elke requirement hieronder is te herleiden tot één van die vijf stappen. Het vertrouwensmechanisme (confidence score → human review) is de spil waar de hele propositie op steunt (NFR-05, FR-12/13) — dat wordt dus als eerste in de flow-diagrammen expliciet gemaakt.

### 1.2 Actoren en hun belang per processtap

| Actor | Intake | Classificatie/Extractie | Review | Communicatie | Dossier |
|---|---|---|---|---|---|
| Eindklant | stuurt document/bericht | — | — | ontvangt follow-up | — |
| Accountant/staff | — | — | corrigeert, keurt goed | keurt bericht goed vóór verzending | leest dossiersamenvatting |
| Kantoor-owner | — | — | ziet volume/nauwkeurigheid | — | ziet tijdswinst (FR-50/51) |
| Systeem (AI) | dedupliceert, matcht sender | classificeert, extraheert, scoort confidence | routeert naar queue | stelt bericht op (concept) | groepeert, vat samen |

### 1.3 MVP-kritieke slice (uit sectie 10 van de requirements-analyse)

De bouwvolgorde is niet toevallig — het is de minimale keten die een echte pilot draagbaar maakt:

FR-01 (email intake) → FR-05 (raw file bewaren) → FR-06 (sender matching) → FR-10 (classificatie) → FR-11 (extractie) → FR-12 (confidence per veld) → FR-13 (routing naar review) → FR-20 (reviewscherm)

Alles daarna (WhatsApp, follow-up automatisering, dossier-export, dashboards) is waardevol maar niet blocking voor "kunnen we een echte pilot draaien."

### 1.4 Requirements gegroepeerd per systeemzone

**Zone A — Intake (FR-01 t/m FR-07)**
Meerdere kanalen (email verplicht, upload-form verplicht, WhatsApp gewenst) monden uit in één immutable `InboundItem`. Deduplicatie en sender-matching gebeuren hier, vóór er iets geïnterpreteerd wordt. Onbekende afzenders worden éénmalig aan een mens voorgelegd (FR-07) — geen stille aannames.

**Zone B — Classificatie & Extractie (FR-10 t/m FR-15)**
AI labelt het documenttype en trekt velden uit, met een confidence score *per veld*, niet per document (FR-12) — dat granulariteitsniveau is bewust, want één zwak veld op een verder correcte factuur moet niet het hele document laten blokkeren. Drempelwaarde is instelbaar per kantoor/veldtype (FR-14, Could — pas na echte data tunebaar, zie open vraag in project-overview).

**Zone C — Human Review (FR-20 t/m FR-23)**
De correctie-actie zelf is UX-kritiek: onder 3 clicks (FR-21). Elke correctie wordt gelogd tegen de originele AI-output (FR-22) — dit is niet alleen audit, het is de databron om drempelwaarden later te tunen.

**Zone D — Klantcommunicatie (FR-30 t/m FR-33)**
Follow-up wordt door AI gedetecteerd en gedraft, maar in de pilotfase nooit automatisch verzonden (FR-31) — mens keurt goed. Dit is een bewuste vertrouwens-governor, geen tijdelijke beperking om lichtzinnig te schrappen.

**Zone E — Dossier/Case (FR-40 t/m FR-42)**
Groepering per klant per periode; samenvatting van wat binnen is, wat ontbreekt, wat nog review nodig heeft. Dit is het eindpunt waar de accountant het systeem "voelt werken."

**Zone F — Reporting (FR-50, FR-51)**
Dit is niet een nice-to-have dashboard — het ís het verkoopbewijs van de pilot (acceptatiecriterium 2, sectie 9 requirements-analyse). Tijd-bespaard-tracking moet vanaf dag 1 meelopen, niet achteraf toegevoegd worden.

### 1.5 Niet-functionele randvoorwaarden die het ontwerp sturen

- **Multi-tenant vanaf dag 1** (NFR-06) — elke diagram-component moet `org_id`-scoped gedacht worden, ook al is er in de pilot maar 1-2 kantoren.
- **EU-data-residency** (NFR-01) — bepaalt waar storage/AI-calls fysiek mogen draaien; relevant voor de architectuurkeuzes (vb. welke LLM-provider/regio).
- **Graceful degradation** (NFR-05) — er mag structureel geen "dead end" in de flow bestaan; elke fout-tak moet naar de human queue leiden, nooit naar niets.
- **Config-only onboarding** (NFR-07) — nieuwe kantoren toevoegen mag geen code-wijziging vereisen; dit dwingt een generieke `Source`/`Organization`-configuratielaag af in plaats van kantoor-specifieke scripts.

### 1.6 Wat expliciet buiten scope blijft (en waarom dat de diagrammen simpel houdt)

Geen integratie met Yuki/Silverfin/Exact, geen automatische indiening bij overheid, geen financieel advies. Dit betekent: de architectuurdiagram heeft geen uitgaande koppeling naar kantoor-boekhoudsoftware — het systeem levert output aan een mens, niet aan een ander systeem. Dat houdt de MVP-architectuur bewust dun.

### 1.7 Open vragen die de diagrammen (nog) niet definitief maken

- Auto-match vs. human-confirm bij eerste contact van een afzender — huidige neiging is human-confirm eerste keer, daarna auto (beïnvloedt Zone A flow-detail).
- Exacte confidence-drempel per veldtype — pas bepaalbaar na echte extractiedata.
- WhatsApp: Should of Must — hangt af van validatiegesprekken.

Deze vragen zijn in de diagrammen gemarkeerd als variabel/config-punt, niet hardcoded verondersteld.

---

## 2. Storyboards

Elk storyboard volgt hetzelfde format: **Trigger → Actoren → Stappen → Systeemrespons → Uitkomst**, telkens getoetst aan de requirement-ID's die het scenario dekt.

### Storyboard 1 — Van binnenkomend document tot reviewklaar

**Dekt:** FR-01, FR-02, FR-04, FR-05, FR-06, FR-10 t/m FR-13, FR-20, FR-21, FR-22

**Trigger:** Een eindklant (zelfstandige) stuurt een factuur naar het kantoor.

**Actoren:** Eindklant, Systeem (AI), Accountant/staff

**Stappen:**

1. Eindklant mailt een PDF-factuur naar het gemonitorde kantoor-inbox-adres (FR-01), of laadt ze op via het login-vrije webformulier (FR-02).
2. Systeem ontvangt het item, controleert op basis van het kanaal-native bericht-ID of dit al eerder verwerkt is (FR-04) — zo niet, wordt het originele bestand ongewijzigd weggeschreven als immutable `InboundItem` (FR-05).
3. Systeem probeert de afzender (e-mailadres) te matchen aan een bekende `Client`. Match gevonden → gekoppeld aan het juiste kantoor-dossier (FR-06). Geen match → item gaat naar een eenmalige bevestigingswachtrij in plaats van te gokken (FR-07).
4. Systeem classificeert het document (factuur/bon/vraag/onduidelijk — FR-10) en extraheert velden: leverancier, bedrag, datum, BTW-nummer (FR-11).
5. Elk geëxtraheerd veld krijgt een individuele confidence score (FR-12). Velden onder de drempel worden gemarkeerd; het hele item gaat naar de human review queue zodra minstens één veld onder de drempel zit (FR-13).
6. Accountant opent het reviewscherm: origineel document en geëxtraheerde velden naast elkaar (FR-20). Correcties kosten maximaal 3 clicks per veld (FR-21).
7. Elke correctie wordt weggeschreven gekoppeld aan de originele AI-output, niet als overschrijving (FR-22) — dit voedt later de accuracy-tracking en drempel-tuning.

**Systeemrespons bij fout:** als extractie volledig faalt (bv. onleesbare scan), landt het item alsnog in de review queue met "extractie mislukt" als status — nooit stil verworpen (NFR-05).

**Uitkomst:** Het document is correct geclassificeerd, de velden zijn geverifieerd door een mens, en het item is klaar om in een dossier gegroepeerd te worden. De correctie is gelogd voor toekomstige accuracy-analyse.

---

### Storyboard 2 — Ontbrekend document: automatische opvolging naar eindklant

**Dekt:** FR-30, FR-31, FR-32

**Trigger:** Het systeem detecteert dat een dossier voor de lopende periode een verwacht document mist (bv. een periodieke bankafschrift of een factuur die normaal maandelijks binnenkomt).

**Actoren:** Systeem (AI), Accountant/staff, Eindklant

**Stappen:**

1. Systeem vergelijkt de dossierstatus tegen het verwachtingspatroon van die klant/periode en signaleert een ontbrekend of onvolledig document (FR-30, deel 1).
2. Systeem stelt automatisch een opvolgbericht op ("we missen nog uw bankafschrift van juni") — dit blijft een concept, geen verzonden bericht (FR-30, deel 2).
3. Concept verschijnt in een goedkeuringswachtrij bij de accountant/staff. Verzending gebeurt pas na expliciete menselijke goedkeuring — dit is in de pilotfase een harde regel, geen suggestie (FR-31).
4. Na goedkeuring verzendt het systeem het bericht via het oorspronkelijke kanaal (e-mail/WhatsApp) en registreert verzendstatus.
5. Systeem houdt bij of het bericht geopend is (indien technisch meetbaar) en of het geresulteerd heeft in het ontvangen document (resolved) (FR-32).
6. Zodra het ontbrekende document alsnog binnenkomt, wordt het gekoppeld aan dezelfde opvolgactie en gemarkeerd als opgelost.

**Systeemrespons bij geen reactie:** item blijft zichtbaar als "open opvolging" in het dossieroverzicht (koppeling met Storyboard 3) — geen stille escalatie, wel zichtbare status voor de accountant.

**Uitkomst:** De eindklant krijgt een tijdige, correct geformuleerde herinnering zonder dat een accountant handmatig hoefde te schrijven — maar zonder dat het systeem ooit ongecontroleerd naar een klant communiceert.

---

### Storyboard 3 — Dossiervoorbereiding voor de accountant

**Dekt:** FR-40, FR-41, FR-42, FR-50, FR-51

**Trigger:** Einde van de periode nadert (bv. maandafsluiting) en de accountant wil weten of het dossier van een klant klaar is om te verwerken.

**Actoren:** Accountant/staff, Systeem, (indirect) Kantoor-owner

**Stappen:**

1. Systeem groepeert alle inbound items van die klant voor de relevante periode automatisch tot één dossier/case (FR-40) — dit gebeurt doorlopend, niet pas op aanvraag.
2. Accountant opent de dossiersamenvatting: wat is binnen (met status: geverifieerd/nog in review), wat ontbreekt nog (gekoppeld aan eventuele lopende opvolgacties uit Storyboard 2), en wat vereist nog menselijke review (FR-41).
3. Indien het dossier klaar is voor verwerking, exporteert de accountant een samenvatting (PDF of gestructureerde notitie) die als werkbasis dient voor de boeking in Yuki/Silverfin/Exact — de export is het eindpunt van dit systeem, er is geen directe koppeling naar die software (FR-42).
4. Parallel registreert het systeem hoeveel van de items in dit dossier automatisch verwerkt zijn versus handmatig behandeld moesten worden (FR-50).
5. Kantoor-owner ziet dit terug in een periodiek (dagelijks/wekelijks) dashboard of rapport met volume, nauwkeurigheid en tijdswinst per kantoor (FR-51) — dit is het bewijsmateriaal voor het pilot-succescriterium.

**Uitkomst:** De accountant hoeft niet zelf te reconstrueren wat compleet is; het systeem levert een kant-en-klaar overzicht. De kantoor-owner krijgt tegelijk het kwantitatieve bewijs dat de tijd die dit bespaart, meetbaar en verdedigbaar is.

---

## 3. Traceability-overzicht (storyboard → requirement → diagram)

| Storyboard | Requirements gedekt | Diagram in `02-diagrammen.md` |
|---|---|---|
| 1. Intake → Review | FR-01–07, FR-10–13, FR-20–22 | Flow A: Intake–Classificatie–Review |
| 2. Opvolging eindklant | FR-30–32 | Flow B: Follow-up & Approval |
| 3. Dossiervoorbereiding | FR-40–42, FR-50–51 | Flow B (aansluitend) + Architectuurdiagram (Reporting-component) |

Zie `02-diagrammen.md` voor de Mermaid system flow-diagrammen en het high-level architectuurdiagram die op dit document voortbouwen.
