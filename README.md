# SkyWatch Radar for Home Assistant

Een tabletvriendelijke Canvas-radar met vliegtuigposities uit ADSB.fi Open Data. De integratie haalt centraal maximaal eenmaal per 10 seconden op; elk dashboard leest alleen de lokale cache.

## HACS: snelle installatie

Dit is een HACS-klaar **Integration**-pakket. Na installatie levert de integratie de radarcode en de wereldwijde kaarttegels zelf aan; er hoeft niets naar `/config/www` te worden gekopieerd.

1. Zet de inhoud van dit pakket in de hoofdmap van een GitHub-repository.
2. Voeg de repository in HACS toe als **Custom repository → Integration** en installeer **SkyWatch Radar**.
3. Herstart Home Assistant en voeg daarna de integratie **SkyWatch Radar** toe via **Instellingen → Apparaten & diensten**.
4. Registreer éénmaal bij **Instellingen → Dashboards → Bronnen** als type **JavaScript-module**:

   ```text
   /skywatch-radar-assets/skywatch-radar.js?v=2.1.1
   ```

5. Maak een dashboard met `dashboard/skywatch-radar-dashboard.yaml`.

De resource- en dashboardstap is bewust handmatig: HACS installeert code, maar hoort niet autonoom de persoonlijke Lovelace-configuratie van een gebruiker te wijzigen. Zie ook `HACS-INSTALL.md`.

## Wat dit pakket bevat

- `custom_components/skywatch_radar/`: de Home Assistant-integratie met configuratiescherm, validatie, foutafhandeling, cache en WebSocket-endpoint.
- `custom_components/skywatch_radar/static/`: de Lovelace Canvas-kaart en 401 wereldwijde tegels met kust-, landsgrens- en meerlijnen. De kaart laadt alleen de tegels rond het gekozen centrum.
- `dashboard/skywatch-radar-dashboard.yaml`: een generiek dashboard voor de kaart.

## Eisen en grenzen

- Home Assistant 2024.7 of nieuwer.
- ADSB.fi Open Data is de enige vluchtbron. Gebruik uitsluitend volgens de actuele voorwaarden van ADSB.fi, waaronder persoonlijk en niet-commercieel gebruik.
- Internettoegang vanaf Home Assistant naar `opendata.adsb.fi`.
- Dit is een radarvisualisatie, niet geschikt voor navigatie, luchtvaartveiligheid of juridische grensbepaling.

## Centrum voor je eigen regio

Open na installatie **Instellingen → Apparaten & diensten → SkyWatch Radar → Configureren**. Vul breedtegraad en lengtegraad in als decimale graden, bijvoorbeeld `52.10095` en `5.64622`. De integratie pollt vervolgens ADSB.fi rond dat punt. Het kaartbereik bij openen is 150 km en kan op de kaart worden aangepast tot het maximale bereik dat je in de integratie instelt.

Op de radarkaart kan een beheerder ook **centrum** tikken, de kaart naar de gewenste positie slepen en bij loslaten de voorgestelde coördinaten bevestigen. De kaart toont tijdens het slepen een tijdelijk kruis; pas na bevestiging wordt het centrum in de integratie opgeslagen en laadt de centrale poll opnieuw. Tik opnieuw op **centrum** of kies *Annuleren* om zonder wijziging terug te keren naar de normale vliegtuigdetails.

## Contactlegenda

Tik op **legenda** op de kaart voor de betekenis van de vier labelregels: callsign; flight level en grondsnelheid; koers en verticale snelheid; ICAO-vliegtuigtype. `---` betekent dat ADSB.fi die waarde niet heeft geleverd. Een felwitte, compacte pijl is een recente radarblip.

## Bronnen en licenties

- Vluchtdata: [ADSB.fi Open Data](https://github.com/adsbfi/opendata).
- Wereldwijde landsgrenzen, kust en meerlijnen: [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/) (publiek domein), vereenvoudigd voor een radarweergave.
- Markermeer-geometrie: © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), eenmalig opgehaald en lokaal gecompileerd; ODbL.

De bronvermelding blijft zichtbaar in de kaart.

## Verificatie voor gebruik

Controleer na installatie dat `sensor.skywatch_radar` de status `online` heeft, dat de kaart vliegtuigen toont en dat de browserconsole geen fout voor `skywatch-radar.js` meldt.
