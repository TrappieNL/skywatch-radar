# SkyWatch Radar via HACS

## Wat HACS automatisch doet

HACS installeert de complete integratie in `custom_components/skywatch_radar`. Daarin zitten ook de Canvas-kaart en de wereldwijde kaarttegels. Na een Home Assistant-herstart worden die veilig aangeboden onder `/skywatch-radar-assets/`; er zijn geen handmatige bestandskopieën naar `/config/www` nodig.

## Eenmalige gebruikersstappen

1. Voeg de GitHub-repository toe in HACS als **Custom repository**, categorie **Integration**.
2. Installeer **SkyWatch Radar** en herstart Home Assistant.
3. Voeg de integratie toe via **Instellingen → Apparaten & diensten** en kies radarcentrum plus maximaal bereik.
4. Registreer onder **Instellingen → Dashboards → Bronnen** één module-resource:

   ```text
   /skywatch-radar-assets/skywatch-radar.js?v=2.1.1
   ```

5. Maak een nieuw dashboard en plak de inhoud van `dashboard/skywatch-radar-dashboard.yaml` in de ruwe configuratie-editor.

Daarna verschijnt de radar in de zijbalk. Bij een update verzorgt HACS de integratiebestanden; verhoog de queryversie van de resource wanneer een browser een oudere kaartcode vasthoudt.

## Grenzen

HACS kan de Lovelace-resource en een persoonlijk dashboard niet automatisch toevoegen zonder de dashboardconfiguratie van de gebruiker te wijzigen. Daarom blijven stappen 4 en 5 zichtbaar en controleerbaar. De radar blijft een visualisatie, niet geschikt voor luchtvaartnavigatie of veiligheidstoepassingen.
