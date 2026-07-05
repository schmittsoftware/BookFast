# SE Lifecycle — Fase 1: System Flow & Architectuurdiagrammen
### AI-diensten voor Boekhoudkantoren — MVP/Pilot

Bouwt voort op `01-requirements-en-storyboards.md`. Diagrammen zijn in Mermaid-syntax — te renderen in VS Code (Mermaid-extensie), GitHub, Obsidian, of via mermaid.live. Elk diagram verwijst naar de requirement-ID's die het dekt.

---

## Diagram A — System Flow: Intake → Classificatie → Review

**Dekt:** FR-01–07, FR-10–15, FR-20–22, NFR-05

```mermaid
flowchart TD
    A1[Eindklant: email] -->|FR-01| B[Intake-laag]
    A2[Eindklant: webformulier] -->|FR-02| B
    A3[Eindklant: WhatsApp - Should] -->|FR-03| B

    B --> C{Dedupe op<br/>kanaal-bericht-ID<br/>FR-04}
    C -->|Duplicaat| Z1[Genegeerd, gelogd]
    C -->|Nieuw| D[Sla origineel op<br/>als immutable InboundItem<br/>FR-05]

    D --> E{Afzender bekend?<br/>FR-06}
    E -->|Ja| F[Koppel aan Client/Org]
    E -->|Nee| G[Eenmalige bevestigings-<br/>wachtrij - FR-07]
    G --> F

    F --> H[AI: classificatie<br/>factuur/bon/vraag/onduidelijk<br/>FR-10]
    H --> I[AI: veldextractie<br/>vendor, bedrag, datum, BTW<br/>FR-11]
    I --> J[Confidence score<br/>per veld - FR-12]

    J --> K{Elk veld boven<br/>drempel? - FR-13/14}
    K -->|Ja, alles OK| L[Auto-goedgekeurd<br/>naar Dossier]
    K -->|Nee, of extractie mislukt| M[Human Review Queue<br/>NFR-05: nooit stil verworpen]

    M --> N[Reviewscherm:<br/>origineel + velden naast elkaar<br/>FR-20]
    N --> O[Accountant corrigeert<br/>max 3 clicks - FR-21]
    O --> P[Correctie gelogd tegen<br/>originele AI-output - FR-22]
    P --> L

    L --> Q[(Dossier/Case<br/>zie Diagram B)]

    style D fill:#e8f4ea,stroke:#4a8f5c
    style M fill:#fdf0e0,stroke:#c98a2e
    style Q fill:#e6eefc,stroke:#3a6bc4
```

**Ontwerpnotitie:** de tak "extractie mislukt" (K → M) is bewust dezelfde queue als lage confidence — er is geen apart foutpad, precies om NFR-05 (nooit stil verworpen) af te dwingen zonder een tweede foutafhandelingssysteem te bouwen.

---

## Diagram B — System Flow: Opvolging & Dossiervoorbereiding

**Dekt:** FR-30–32, FR-40–42, FR-50–51

```mermaid
flowchart TD
    Q[(Dossier/Case)] --> R[Periodieke check:<br/>verwacht vs. aanwezig<br/>FR-40]
    R --> S{Document<br/>ontbreekt?}
    S -->|Nee| T[Dossier compleet]
    S -->|Ja| U[AI stelt opvolgbericht op<br/>concept - FR-30]

    U --> V{Accountant<br/>keurt goed?<br/>FR-31 - verplicht in pilot}
    V -->|Nee, aanpassen| U
    V -->|Ja| W[Verzend via origineel kanaal]

    W --> X[Track: verzonden/geopend/<br/>opgelost - FR-32]
    X --> Y{Document alsnog<br/>ontvangen?}
    Y -->|Ja| T
    Y -->|Nee, na tijd| X

    T --> AA[Dossiersamenvatting:<br/>in / ontbreekt / in review<br/>FR-41]
    AA --> AB[Export PDF /<br/>gestructureerde notitie<br/>FR-42]
    AB --> AC[Accountant verwerkt<br/>handmatig in Yuki/Silverfin/Exact<br/>- géén directe koppeling]

    Q -.-> AD[Tel: auto-verwerkt vs.<br/>handmatig - FR-50]
    AD --> AE[Dashboard/rapport:<br/>volume, nauwkeurigheid, tijd<br/>FR-51]
    AE --> AF[Kantoor-owner:<br/>bewijs voor pilot-succes]

    style V fill:#fdf0e0,stroke:#c98a2e
    style AC fill:#f2f2f2,stroke:#888
    style AE fill:#e6eefc,stroke:#3a6bc4
```

**Ontwerpnotitie:** het blok `AC` (verwerking in Yuki/Silverfin/Exact) staat bewust buiten dit systeem getekend — er loopt geen pijl terug het systeem in. Dat is de expliciete MVP-grens uit sectie 6/8 van de requirements: geen API-koppeling naar de kantoorsoftware.

---

## Diagram C — High-Level Architectuur (MVP)

**Dekt:** NFR-01, NFR-02, NFR-03, NFR-06, NFR-07, sectie 6 (Integratie)

```mermaid
flowchart LR
    subgraph CH["Intake-kanalen"]
        direction TB
        E1[Email / IMAP]
        E2[Webformulier]
        E3[WhatsApp Business API<br/>Should-have]
    end

    subgraph CORE["Kernsysteem — multi-tenant, org_id op elke entiteit (NFR-06)"]
        direction TB
        ING[Ingestion Service<br/>dedupe, sender-match]
        RAW[(Raw Storage - EU-region<br/>immutable InboundItem + Attachment<br/>NFR-01)]
        AI[AI Classificatie & Extractie<br/>LLM API - managed service]
        EXT[(ExtractedData store<br/>flexible JSON + confidence + status)]
        REV[Review Queue + UI]
        COMM[Communicatie-module<br/>concept-generatie + approval-gate]
        DOS[Dossier/Case-module]
        REP[Reporting / Dashboard]
        AUD[(AuditLog<br/>NFR-03: wie/wat/wanneer)]
        CFG[(Organization / Source config<br/>NFR-07: config-only onboarding)]
    end

    subgraph OUT["Output naar mens - geen systeemkoppeling"]
        ACC[Accountant / Kantoor-owner]
        CLI[Eindklant]
    end

    E1 --> ING
    E2 --> ING
    E3 --> ING

    ING --> RAW
    ING --> AI
    AI --> EXT
    EXT --> REV
    REV -->|correcties| AUD
    REV --> DOS
    EXT -->|hoge confidence| DOS

    DOS --> COMM
    COMM -->|approval verplicht| ACC
    COMM -->|na goedkeuring| CLI

    DOS --> REP
    REP --> ACC

    CFG -.->|stuurt gedrag van| ING
    CFG -.-> AI
    CFG -.-> COMM

    RAW -.->|niet geïntegreerd met| EXT2[Yuki / Silverfin / Exact<br/>expliciet buiten MVP-scope]

    style RAW fill:#e8f4ea,stroke:#4a8f5c
    style AUD fill:#f2f2f2,stroke:#888
    style CFG fill:#f2f2f2,stroke:#888
    style EXT2 fill:#f9e0e0,stroke:#c44,stroke-dasharray: 5 5
```

**Ontwerpnotities:**

- Alle datastores (`RAW`, `EXT`, `AUD`, `CFG`) liggen binnen de multi-tenant kernsysteem-grens, EU-hosted (NFR-01). Fysieke scheiding tussen `RAW` (immutable, ongewijzigd) en `EXT` (AI-interpretatie) is een architecturale hardheid, geen implementatiedetail — dit staat letterlijk in sectie 8 van het project-overzicht als vastgelegde beslissing.
- `CFG` (Organization/Source-config) stuurt drie andere componenten aan (ingestion-regels, confidence-drempels, communicatie-kanalen) zonder dat er per kantoor code wordt geschreven — dit is de architecturale vertaling van NFR-07.
- De koppeling naar Yuki/Silverfin/Exact is expliciet getekend als *niet bestaand* (stippellijn, rode kleur) om te voorkomen dat een toekomstige lezer van dit diagram die integratie per ongeluk als "gepland" interpreteert.
- Een DPA/verwerkersovereenkomst (NFR-02) is geen technisch blok in dit diagram, maar een randvoorwaarde die vóór elk `E1/E2/E3`-kanaal live gaat voor een kantoor geregeld moet zijn — vermeld hier voor volledigheid, niet als systeemcomponent.

---

## 4. Wat deze diagrammen bewust niet vastleggen

Conform de open vragen in het project-overzicht (sectie 9):

- **Auto-match vs. human-confirm** bij eerste afzendercontact is in Diagram A getekend als expliciete keuze (`E`), maar het exacte gedrag na de eerste keer (blijvend auto-matchen?) is niet vastgelegd — dit is een configuratieparameter, geen architectuurkeuze.
- **Confidence-drempelwaarden** zijn in Diagram A getekend als beslispunt (`K`), niet als vaste waarde — de drempel zelf is per kantoor/veldtype instelbaar (FR-14) en wordt pas na echte pilotdata getuned.
- **WhatsApp (E3)** staat in Diagram C als kanaal getekend maar gemarkeerd Should-have — bouwvolgorde-beslissing, geen architecturale onzekerheid.

---

## 5. Suggestie voor volgende SE-lifecycle stap

Met requirements, storyboards en diagrammen op tafel is de logische vervolgstap een **data-model / entiteitendiagram** (Organization, Source, InboundItem, Attachment, ExtractedData, Client, Case, Action, AuditLog — sectie 5 van de requirements-analyse) en een **API/interface-schets** per module, vóór er code geschreven wordt. Zeg het maar als je daarmee wil verdergaan.
