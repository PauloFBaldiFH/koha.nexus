/* SPDX-License-Identifier: GPL-3.0-or-later */
import java.lang.reflect.Proxy;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;

/** Explicit JDBC doubles; real PostgreSQL/receipt/startup is tested separately. */
public final class NexusSchemaGuardTest {
    private static final String LOCK = "a".repeat(64);

    private static Connection db(int count, String description, boolean success) {
        int[] row = {-1};
        String[] columns = {"1", "10.1", description, "SQL", "migration.sql", "123", success ? "t" : "f"};
        ResultSet result = (ResultSet) Proxy.newProxyInstance(NexusSchemaGuardTest.class.getClassLoader(),
            new Class<?>[]{ResultSet.class}, (p, method, args) -> {
                switch (method.getName()) {
                    case "next": return ++row[0] < count;
                    case "getBoolean": return success;
                    case "getString": return columns[(Integer) args[0] - 1];
                    case "close": return null;
                    default: throw new AssertionError(method.getName());
                }
            });
        PreparedStatement query = (PreparedStatement) Proxy.newProxyInstance(NexusSchemaGuardTest.class.getClassLoader(),
            new Class<?>[]{PreparedStatement.class}, (p, method, args) -> {
                switch (method.getName()) {
                    case "executeQuery": return result;
                    case "setQueryTimeout":
                    case "close": return null;
                    default: throw new AssertionError(method.getName());
                }
            });
        return (Connection) Proxy.newProxyInstance(NexusSchemaGuardTest.class.getClassLoader(),
            new Class<?>[]{Connection.class}, (p, method, args) -> {
                if (!method.getName().equals("prepareStatement") || !((String) args[0]).startsWith("SELECT ")) {
                    throw new AssertionError("Guard attempted something other than SELECT");
                }
                return query;
            });
    }

    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
        System.out.println("PASS: " + message);
    }

    public static void main(String[] args) throws Exception {
        String original = NexusSchemaGuard.historyFingerprint(db(1, "release", true), LOCK);
        check(original.equals(NexusSchemaGuard.historyFingerprint(db(1, "release", true), LOCK)), "stable migration receipt");
        check(!original.equals(NexusSchemaGuard.historyFingerprint(db(1, "changed", true), LOCK)), "changed migration history refused");
        check(!original.equals(NexusSchemaGuard.historyFingerprint(db(1, "release", true), "b".repeat(64))), "different release lock refused");
        boolean failed = false;
        try { NexusSchemaGuard.historyFingerprint(db(1, "release", false), LOCK); }
        catch (IllegalStateException expected) { failed = true; }
        check(failed, "failed migration refused");
        failed = false;
        try { NexusSchemaGuard.historyFingerprint(db(0, "release", true), LOCK); }
        catch (IllegalStateException expected) { failed = true; }
        check(failed, "empty/uninitialized database refused");
        failed = false;
        try { NexusSchemaGuard.historyFingerprint(db(1, "release", true), "latest"); }
        catch (IllegalStateException expected) { failed = true; }
        check(failed, "missing immutable release identity refused");
    }
}
