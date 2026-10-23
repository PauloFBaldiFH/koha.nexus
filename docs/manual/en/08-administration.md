# 8. Schedules, VPN, messaging and administration

[Manual index](README.md) · [Previous: local AI](07-local-ai.md)

The actions in this chapter affect server operation or communication with patrons. Check the current state before changing settings and retain a recent backup. Configuration alone does not establish that a feature works through the library network: check the result afterwards.

## Schedules and cron

Open **Schedules & cron tasks** from the sidebar or with **s**. Each row has an enable switch, frequency and time. Depending on frequency, it also has a weekday, day of the month or custom expression.

1. Use **Reload** to read current settings.
2. Enable only the required jobs and set the time as `HH:MM`.
3. Use **Preview** to read the file to be written.
4. Use **Save** and confirm the changes summary.
5. Reload and check the saved schedules.

The managed file is `/etc/cron.d/koha_tasks`. The flow retains the previous copy as `koha_tasks.bak`. Disabled jobs remain commented, preserving their time for reactivation. The reader retains custom lines.

**Defaults** places default values on screen; save them to keep them. Defaults include an SQL backup at 23:00 nightly and a MARC export at 03:00 on Sundays. Check the timezone and effective schedule, which the library may have changed.

The server must be on and Linux running at the scheduled time. On Windows, closing or stopping the environment can prevent nightly execution; do not assume the schedule will turn on the computer. Koha's own notices have their own sending mechanism, separate from the additional jobs managed here.

## WireGuard VPN

Open **Security & access hub**, then **WireGuard VPN**, or press **v**. The screen requests a public address or server name and UDP port.

1. Enter the address through which devices will reach the server and check the port.
2. Use **Set up the VPN** and read the network changes in the confirmation. On a network with a router, that UDP port must be forwarded to the server.
3. Name each device and use **Add device**.
4. Select the device and open **QR code & profile** to configure its WireGuard client.
5. Check connectivity and access to the staff interface. The panel shows device activity and traffic.

Each device has its own profile. Do not publish profiles or their QR codes. **Revoke** prevents that profile from connecting again; the device needs a new profile to return. **Turn off** stops the VPN and disconnects devices but keeps profiles, according to its confirmation.

This is a split tunnel: `10.66.0.0/24` goes through the VPN while the device's internet and DNS remain on its own connection. The screen gives staff access at `http://10.66.0.1:8080` when connected. Under WSL without mirrored networking, the code reports that the server is not directly reachable and keeps this VPN disabled.

## Messaging and interoperability

Open **Messaging & interoperability** from the sidebar or press **m**. Current tabs are **E-mail**, **WhatsApp & Telegram**, **SMS**, **Alerts**, **SIP2** and **Z39.50**, translated according to the installation's dictionary.

### E-mail

Enable Koha e-mail through the screen's action and check the default SMTP server. Buttons open Koha's SMTP configuration, library address, notices and slips, and overdue notice rules.

Enabling sending does not fill every circulation rule and recipient. Review the server, patron preferences and notice templates. Follow the provider's authentication instructions without recording private information in public reports.

### WhatsApp, Telegram and SMS

Use **Set up WhatsApp and Telegram** to access service configuration, country and area code settings, test messages, notice activation and phone checks. WhatsApp depends on a gateway; the panel does not make Koha independent of that gateway. Telegram depends on its bot and recipient configuration.

Send a test to an authorised recipient before enabling production notices. Check telephone formats and Koha notice templates. Do not apply batch telephone corrections without reading the preview.

The **SMS** tab leads to `SMSSendDriver` and patron messaging preferences. It depends on a compatible driver and service; entering a driver name alone does not guarantee sending.

### Additional alerts

The **Alerts** tab supports due-date reminders, overdue alerts, repeat intervals and a daily summary for the library. Choose channels and save. **Dry run (sends nothing)** shows a simulation without sending messages.

When an alert is enabled, the flow enables its scheduled job. Check cron too. Koha's own notices can send similar messages: choose a policy that avoids duplicate reminders for the same event.

### SIP2 and Z39.50

The **SIP2** tab configures the self-check device's port, network, library and permissions. Check the option to remove examples and use the button to create the required Koha account. Server configuration and the device's account must correspond, as instructed on screen. Do not expose the port to all networks merely for a local test.

The **Z39.50** tab leads to the server screen described in chapter 5. Querying external sources and making your catalogue available to others are different operations.

## Security and remote access

Security & access hub also includes Cloudflare Tunnel, UFW rules, restriction of staff port 8080, HTTPS and Fail2ban. Read the state and summary for each action before confirming. Tunnel, VPN and direct port access have different settings and reach.

Restricting port 8080 limits direct staff access while retaining your chosen remote access strategy. Do not change a remote server's rules without knowing how you will continue administering it.

**To confirm:** domain, router, internet provider and institutional requirements for publishing the service. Source code alone cannot establish these. This manual therefore does not give one publication recipe for every network.

## Settings, languages and updates

Under **Koha settings & parameters**, sizing adjusts memory and workers, super librarian creation provides an account with broad permissions, and clock configuration lets you select the timezone. Reserve administrative permissions for those who need them.

Under **Koha languages**, separate actions download and activate, download only, activate an installed language and list languages. Downloading a pack does not necessarily activate it. Check the result in the panel, staff interface and OPAC.

In **Update center**, distinguish updating system packages and Koha schemas from updating the panel itself through GitHub. Make a backup and reserve a maintenance window. A panel update can end the session so the next launch loads the new version. If schema migration fails, do not assume a restart has resolved it: inspect the error and diagnostics.

## Library administration tools

**Library tools** includes authority synchronisation and linking, duplicate author searches, SQL reports, patron category changes, quality checks and privacy routines.

- For category changes, choose different source and destination categories, the selection rule and library. Read the dry run before confirming the change with a backup.
- Quality checks find inconsistencies; the operation is read-only and does not automatically repair every reported problem.
- History anonymisation removes links between old records and patrons according to Koha's flow. It does not erase the complete bibliographic history.
- Deleting old patrons requires filters, a dry run and confirmation using the displayed count. This is destructive. Check retention policy before accepting.
- Duplicate author searches present possible variants for review; similar names do not prove two authorities represent the same person.

Cataloguing tools hidden in the current menu are not presented here as available cards. For logs and failure investigation, continue to the next chapter.

## Checked sources

- [Menus](../../../panel/kei_panel/menus.py), visible and hidden actions.
- [Schedules](../../../panel/kei_panel/views/crons.py) and [cron reader](../../../panel/kei_panel/cron.py), preview, defaults and saving.
- [VPN](../../../panel/kei_panel/views/vpn.py), setup, devices, revocation and WSL limitations.
- [Messaging](../../../panel/kei_panel/views/hub.py), tabs, alerts, SMTP, SIP2 and Koha links.
- [Settings](../../../panel/kei_panel/routines/settings.py), [security](../../../panel/kei_panel/routines/security.py) and [general actions](../../../panel/kei_panel/routines/tools.py).
- [Installer](../../../installer), updates, messaging, categories, quality, privacy and authorities.
