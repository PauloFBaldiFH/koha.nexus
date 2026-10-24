Koha.Nexus Privacy Policy

Koha.Nexus installs and manages the Koha library system on the library's own computer. This policy says what data stays there, what is sent to services run by the developer (Paulo F. Baldi Filho), and what is sent to other services the library chooses. The developer does not sell or share any data, and does not use it for advertising.

1. Data that stays on the library's computer
Koha keeps the library's data (catalogue, patrons, loans, staff accounts) in a database inside WSL 2 on the library's computer, and backups are saved there too. The library controls this data. Koha.Nexus never sends patron data to the developer.

2. Data sent to koha.nexus services run by the developer
- Catalogue searches: Koha.Nexus adds the koha.nexus search services (sru.koha.nexus and catalog.koha.nexus) to Koha's cataloguing search. When staff search for a record there, the search terms (such as a title, author or ISBN) and the computer's IP address reach these services. They are used only to answer the search and to keep the services running and protected.
- Free address (optional): when the library asks for a free address, the institution name, a contact e-mail, the chosen address and, if given, its CNPJ are sent to broker.koha.nexus, together with the IP address. The server then sends a daily status signal. This data is used only to create, run and support the address, and is deleted when the library gives the address up.

3. Data sent to other services, only when the library uses them
- Installation and updates: Debian, the Koha community and GitHub.
- Catalogue searches in other libraries' Z39.50/SRU servers: the search terms go to the catalogues chosen.
- Online catalogue: Cloudflare carries the catalogue's traffic.
- Cloud backup (optional): Google Drive, OneDrive, MEGA or S3, as configured.
- Reader alerts and notices (optional): sent through the library's own e-mail server, or the WhatsApp, Telegram or SMS service it configures, with the patron's contact details and the message.
- AI assistant (optional): staff questions go to the AI service chosen, or stay on the computer with a local model.
Each of these services has its own privacy policy.

4. Choices
Optional features are off until the library turns them on in the control panel, and can be turned off at any time. The koha.nexus search services can be unticked in Koha's Z39.50/SRU servers. Uninstalling Koha.Nexus and removing the "koha" WSL distribution deletes the data from the computer. To ask for data held by a koha.nexus service to be deleted, contact the developer.

5. Contact
Paulo F. Baldi Filho, [contact e-mail], https://koha.nexus

Last updated: October 24, 2026.
