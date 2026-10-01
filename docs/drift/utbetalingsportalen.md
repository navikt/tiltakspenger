# Utbetalingsportalen

Utbetalingsportalen er økonomiavdelingens arbeidsflate mot Oppdragssystemet (OS) og Utbetalingsreskontroen (UR).
Her kontrollerer du om en utbetaling kom fram til Oppdragssystemet og ble utbetalt.

## Sidene vi bruker

| Side | Viser |
| --- | --- |
| Oppdragsinfo | Oppdragene i Oppdragssystemet per person, med fagområde og status. Våre har fagområde `TILTPENG`. |
| Oppslag Reskontro Stønad (ORS) | Posteringene i Utbetalingsreskontroen per person, altså det som er bokført og utbetalt. |

## Miljøer

| Miljø | Reskontro (ORS) | Oppdragsinfo |
| --- | --- | --- |
| Dev (Q1) | <https://utbetalingsportalen.intern.dev.nav.no/ors> | <https://utbetalingsportalen.intern.dev.nav.no/oppdragsinfo> |
| Prod | <https://utbetalingsportalen.intern.nav.no/ors> | <https://utbetalingsportalen.intern.nav.no/oppdragsinfo> |

## Slik kontrollerer du en utbetaling

I prod må du be en saksbehandler med tilgang om å gjøre oppslaget.

1. Finn personens fødselsnummer i saksbehandlingen.
2. Slå opp personen i Oppdragsinfo og finn oppdraget med fagområde `TILTPENG` og riktig periode.
3. Slå opp personen i Oppslag Reskontro Stønad og kontroller posteringen, forfallsdatoen og utbetalingsdatoen.
4. Mangler oppdraget, sjekk utbetalingsstatusen på saken for å se om overføringen feilet hos oss eller ble avvist av Oppdragssystemet.
5. Finnes oppdraget uten postering, sjekk forfallsdatoen og om økonomisystemet har kjørt etter at oppdraget kom fram.

Stegene bygger på dokumentasjonen til sidene og er ikke prøvd.

## Tilgang

Utviklere kan søke om tilgang i dev, men får ikke tilgang i prod.
Tilgangen har tidligere blitt bestilt i #tp-utbetaling, men vi venter på bekreftelse på hvordan det skal gjøres fremover.
Hvilke ressurser som gir tilgang i dev, er ikke avklart.
Spørsmål om sidene går til `#utbetaling`.
