/* SPDX-License-Identifier: GPL-3.0-or-later */
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.dspace.core.Context;
import org.dspace.servicemanager.DSpaceKernelImpl;
import org.dspace.servicemanager.DSpaceKernelInit;
import org.dspace.eperson.EPerson;
import org.dspace.eperson.Group;
import org.dspace.eperson.factory.EPersonServiceFactory;
import org.dspace.eperson.service.EPersonService;
import org.dspace.eperson.service.GroupService;

/** Local root-authorized adapter. Secrets arrive on stdin, never argv or output. */
public final class NexusAdmin {
    private static String line(BufferedReader input) throws Exception {
        String value = input.readLine();
        if (value == null || value.length() > 1024) throw new IllegalArgumentException("Invalid input.");
        return value;
    }
    private static String supportedLanguage(String input) throws Exception {
        String normalized = input.replace('_', '-');
        JsonNode catalog = new ObjectMapper().readTree(Files.readString(
            Path.of("/usr/local/share/nexus-dspace/languages.json"), StandardCharsets.UTF_8));
        for (JsonNode row : catalog.get("languages")) {
            if (row.get("code").asText().equalsIgnoreCase(normalized)) return row.get("code").asText();
        }
        throw new IllegalArgumentException("Unsupported account language.");
    }
    public static void main(String[] args) {
        Context context = null;
        DSpaceKernelImpl kernel = null;
        int code = 0;
        try {
            if (args.length != 1 || !List.of("status", "create", "password").contains(args[0]))
                throw new IllegalArgumentException("Unknown administrative operation.");
            String operation = args[0];
            String email = "", first = "", last = "", language = "", password = "";
            if (!operation.equals("status")) {
                BufferedReader input = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
                email = line(input); first = line(input); last = line(input);
                language = line(input); password = line(input);
                if (!email.matches("[^@\\s|=]+@[^@\\s|=]+\\.[^@\\s|=]+") || password.length() < 10)
                    throw new IllegalArgumentException("Invalid e-mail or password length.");
                if (operation.equals("create")) {
                    if (first.isBlank() || last.isBlank()) throw new IllegalArgumentException("Name is required.");
                    language = supportedLanguage(language);
                }
            }
            // Match the official ScriptLauncher bootstrap before creating a Context.
            kernel = DSpaceKernelInit.getKernel(null);
            if (!kernel.isRunning()) kernel.start();
            context = new Context(operation.equals("status") ? Context.Mode.READ_ONLY : Context.Mode.READ_WRITE);
            EPersonService people = EPersonServiceFactory.getInstance().getEPersonService();
            GroupService groups = EPersonServiceFactory.getInstance().getGroupService();
            Group admins = groups.findByName(context, Group.ADMIN);
            if (admins == null) throw new IllegalArgumentException("Administrator group is missing.");
            ObjectMapper json = new ObjectMapper();
            if (operation.equals("status")) {
                List<String> emails = new ArrayList<>();
                for (EPerson person : groups.allMembers(context, admins)) {
                    if (person.canLogIn() && person.getEmail() != null) emails.add(person.getEmail());
                }
                emails.sort(String::compareTo);
                System.out.println("NEXUS_ADMIN_JSON=" + json.writeValueAsString(
                    Map.of("state", emails.isEmpty() ? "missing" : "own", "admins", emails)));
                context.abort(); context = null;
                return;
            }
            context.turnOffAuthorisationSystem();
            EPerson person = people.findByEmail(context, email);
            if (operation.equals("create")) {
                // Unlike upstream create-administrator, never promote or overwrite an existing person.
                if (person != null) throw new IllegalArgumentException("An account already uses that e-mail; nothing changed.");
                person = people.create(context);
                person.setEmail(email); person.setCanLogIn(true);
                person.setRequireCertificate(false); person.setSelfRegistered(false);
                person.setFirstName(context, first); person.setLastName(context, last);
                person.setLanguage(context, language);
                groups.addMember(context, admins, person);
                groups.update(context, admins);
            } else if (person == null || !person.canLogIn() || !groups.isMember(context, person, admins)) {
                throw new IllegalArgumentException("Only an existing enabled administrator may be reset.");
            }
            people.setPassword(person, password);
            people.update(context, person);
            context.complete(); context = null;
            System.out.println("NEXUS_ADMIN_JSON={\"changed\":true}");
        } catch (IllegalArgumentException error) {
            System.err.println(error.getMessage()); code = 65;
        } catch (Exception error) {
            System.err.println("Administrative operation failed; no password is included in diagnostics.");
            code = 70;
        } finally {
            if (context != null && context.isValid()) context.abort();
            if (kernel != null) kernel.destroy();
        }
        if (code != 0) System.exit(code);
    }
}
