# tiltakspenger

Startpunkt (metarepo) for tiltakspenger

## Komme i gang

[meta](https://github.com/mateodelnorte/meta) brukes til å sette opp
repositories for alle repoene.

Enn så lenge må du sørge for å ha `npm` installert (`brew install node`).

```
npm install meta -g --no-save
```

Merk! meta foran vanlig clone-kommando:

```
meta git clone git@github.com:navikt/tiltakspenger.git
```

Nå kan git brukes som normalt for hvert repo.

Se [meta](https://github.com/mateodelnorte/meta) for flere kommandoer.

Dersom du nå åpner `build.gradle` med `Open` (som Project) i IntelliJ så får du alle komponentene inn i ett
IntelliJ-oppsett.

Repoene som er inkludert i dette meta-repoet er

- [tiltakspenger-iac] (https://github.com/navikt/tiltakspenger-iac)
- [tiltakspenger-libs] (https://github.com/navikt/tiltakspenger-libs)
- [tiltakspenger-mottak] (https://github.com/navikt/tiltakspenger-mottak)
- [tiltakspenger-arena] (https://github.com/navikt/tiltakspenger-arena)
- [tiltakspenger-person] (https://github.com/navikt/tiltakspenger-person)
- [tiltakspenger-fp] (https://github.com/navikt/tiltakspenger-fp)
- [tiltakspenger-ufore] (https://github.com/navikt/tiltakspenger-ufore)
- [tiltakspenger-institusjon] (https://github.com/navikt/tiltakspenger-institusjon)
- [tiltakspenger-skjerming] (https://github.com/navikt/tiltakspenger-skjerming)
- [tiltakspenger-vedtak] (https://github.com/navikt/tiltakspenger-vedtak)
- [tiltakspenger-vedtak-rivers] (https://github.com/navikt/tiltakspenger-vedtak-rivers)
- [tiltakspenger-testmeldinger] (https://github.com/navikt/tiltakspenger-testmeldinger)
- [tiltakspenger-saksbehandler] (https://github.com/navikt/tiltakspenger-saksbehandler)
- [tiltakspenger-scheduler] (https://github.com/navikt/tiltakspenger-scheduler)
- [tiltakspenger-template] (https://github.com/navikt/tiltakspenger-template)
- [tiltakspenger-admin] (https://github.com/navikt/tiltakspenger-admin)

```mermaid
  graph TD;
      A-->B;
      A-->C;
      B-->D;
      C-->D;
```
