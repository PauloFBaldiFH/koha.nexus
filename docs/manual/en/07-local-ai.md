# 7. Local AI and assistance tools

[Manual index](README.md) · [Previous: appearance](06-appearance.md)

The **AI** screen, opened with **a**, brings together provider configuration, Ollama on this server and two tools: image-based cataloguing in MARC Replace and an assistant on the staff home page. Configuring the provider does not automatically install every tool.

## Configure Ollama

1. Open AI and read the performance warning. Local processing can consume much of the CPU and RAM and slow Koha down.
2. In **Ollama on this server**, use **Check Ollama**. If it is not installed, use **Install Ollama** and wait for the result.
3. Choose a model from the panel's list and use **Download**. Downloading requires network access and free space. This manual does not prescribe model names, because the list and availability can change.
4. Select **Local Ollama** as provider and check the server URL. The default local address is `http://127.0.0.1:11434`.
5. Use **Use for chat** or **Use for cataloguing**, according to purpose. Photo cataloguing requires vision capability; a text-only model cannot read images.
6. Use **Test connection** and **Save**. Filling a field does not save it. Screen shortcuts are **F5** to test and **Ctrl+S** to save.

An empty chat field uses the vision selection, according to the configuration. **Load models** queries the provider's list; the screen says when it uses a built-in list because it cannot query the server.

**Installed** and **in memory** are different states. A downloaded model occupies disk; when loaded to answer, it also occupies RAM. **Free memory** unloads models without deleting downloads. Ollama can load them again for the next request.

The Ollama box remains available even when another provider is selected. To ensure a tool actually uses local processing, check its saved provider and URL. Do not assume a query was local merely because Ollama is installed.

## Use MARC Replace and photo cataloguing

In the tools area, install or update the MARC replacement page and open **MARC Replace**. The installer checks that the page compiles with Koha and asks about staff interface shortcuts.

The page handles one record at a time. To replace from a file or text:

1. Select the `.mrc` or `.xml`, or paste the record text.
2. Enter the `biblionumber` of the existing record to replace. Leaving it empty is the route for adding a new record; check the preview to avoid accidental duplication.
3. Use **Preview** and compare the current version with the proposal.
4. Confirm only after checking the title's identity and bibliographic fields.

Items of a replaced record are preserved; item fields in the incoming file are excluded. The previous version is saved and can be downloaded as MARCXML. To recover it, the page instructs you to submit that version for the same `biblionumber`. This does not replace a full database backup.

In the **AI cataloguing** tab:

1. Send legible photos of the cover, title page and verso of the title page, as available. The page accepts JPEG, PNG and WebP and requires at least one image.
2. Choose the new record's framework or identify the record to replace, as intended.
3. Use **Read the photos** and wait for the draft.
4. Compare the draft with the images. Check title, responsibility, publication, ISBN, classification and information that could not be read.
5. Correct the MARC text before confirming the write.

AI-suggested classification must be reviewed in the schedules adopted by the library. A correct ISBN check digit does not establish that it matches the edition. The page warns about missing information and does not save item fields from this draft.

## Assistant on the staff home page

Use **Install, update or remove the assistant** to manage the tool. Installation places the chat where the staff home page's news block was; OPAC news is unaffected.

The assistant searches through Koha's engine and application-defined read queries. It does not execute unrestricted SQL written by AI. Responses can contain record links and action proposals.

**A proposal is not yet an executed change.** Check the record, current and proposed values, and the operation's effect. Execution requires **Approve & Execute** and respects the librarian's permissions. If the record has changed since the proposal, the flow can refuse it and request a new one.

An option lets you consult changes confirmed in the assistant. Clearing a conversation or removing the assistant does not undo every approved action. Removal deletes saved conversations and retains the confirmed-change record, as described by the panel's notice.

## Performance and confidentiality

Use local AI at a time when you can monitor CPU, memory and Koha responsiveness. If the server becomes slow, avoid starting more photo requests and free memory when appropriate. The inspected code does not guarantee response time on every computer.

A remote provider receives data sent in its requests. Before using it, assess the library's policy for personal data and images. Do not send patron data merely to test chat. Cost labels in the list are interface guidance, not a provider guarantee of free access.

## Point to confirm

**To confirm:** RAM, disk and response-time requirements for each local processing choice. Requirements depend on the selected model and hardware; Koha's installation minimum does not guarantee AI performance.

## Checked sources

- [AI screen](../../../panel/kei_panel/views/ai.py), fields, buttons, shortcuts, checks, download and memory release.
- [MARC Replace integration](../../../panel/kei_panel/marcreplace.py), opening and managing the page.
- [Installer](../../../installer), `function_marc_replace`, generated page text and implementation, `function_ai_assistant`, installation, proposals and assistant removal.
