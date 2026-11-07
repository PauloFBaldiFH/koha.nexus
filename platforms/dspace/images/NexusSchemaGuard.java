/* SPDX-License-Identifier: GPL-3.0-or-later
 * Local deployment guard, not a modification of DSpace.
 * Uses JDBC directly: loading a DSpace Context here could itself migrate the DB.
 */
import java.io.DataOutputStream;
import java.io.InputStream;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.DigestOutputStream;
import java.security.MessageDigest;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.HexFormat;
import java.util.Properties;

public final class NexusSchemaGuard {
    private static final Path CONFIG = Path.of("/dspace/config/local.cfg");
    private static final Path RECEIPT = Path.of("/dspace/var/nexus-schema.sha256");

    static String historyFingerprint(Connection db, String lock) throws Exception {
        if (lock == null || !lock.matches("[a-f0-9]{64}")) {
            throw new IllegalStateException("Missing release identity");
        }
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        int rows = 0;
        try (var sink = new DataOutputStream(new DigestOutputStream(java.io.OutputStream.nullOutputStream(), hash));
             var query = db.prepareStatement("SELECT installed_rank, version, description, type, script, checksum, success " +
                                            "FROM public.schema_version ORDER BY installed_rank")) {
            sink.writeUTF(lock);
            query.setQueryTimeout(20);
            try (ResultSet data = query.executeQuery()) {
                while (data.next()) {
                    if (!data.getBoolean(7)) {
                        throw new IllegalStateException("Failed migration");
                    }
                    for (int col = 1; col <= 7; col++) {
                        String value = data.getString(col);
                        if (value == null) {
                            sink.writeInt(-1);
                        } else {
                            byte[] bytes = value.getBytes(java.nio.charset.StandardCharsets.UTF_8);
                            sink.writeInt(bytes.length);
                            sink.write(bytes);
                        }
                    }
                    rows++;
                }
            }
        }
        if (rows == 0) {
            throw new IllegalStateException("Uninitialized schema");
        }
        return HexFormat.of().formatHex(hash.digest());
    }

    public static void main(String[] args) {
        try {
            if (args.length != 1 || !(args[0].equals("check") || args[0].equals("record"))) {
                throw new IllegalArgumentException("Expected check or record");
            }
            // Properties is sufficient for the installer's explicit JDBC/user/hex-password values.
            // No Spring, Flyway, DSpace service manager or Context is loaded.
            Properties config = new Properties();
            try (InputStream input = Files.newInputStream(CONFIG)) {
                config.load(input);
            }
            Properties credentials = new Properties();
            credentials.setProperty("user", config.getProperty("db.username"));
            credentials.setProperty("password", config.getProperty("db.password"));
            credentials.setProperty("connectTimeout", "10");
            credentials.setProperty("socketTimeout", "30");
            String fingerprint;
            try (Connection db = DriverManager.getConnection(config.getProperty("db.url"), credentials)) {
                db.setAutoCommit(false);
                db.setReadOnly(true);
                fingerprint = historyFingerprint(db, System.getenv("NEXUS_DSPACE_RELEASE_LOCK"));
                db.rollback();
            }
            if (args[0].equals("record")) {
                Path tmp = Files.createTempFile(RECEIPT.getParent(), ".nexus-schema-", ".tmp",
                                               PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------")));
                try {
                    Files.writeString(tmp, fingerprint + "\n");
                    try (var file = FileChannel.open(tmp, StandardOpenOption.WRITE)) {
                        file.force(true);
                    }
                    Files.move(tmp, RECEIPT, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
                } finally {
                    Files.deleteIfExists(tmp);
                }
            } else if (!MessageDigest.isEqual(fingerprint.getBytes(java.nio.charset.StandardCharsets.US_ASCII),
                       Files.readString(RECEIPT).trim().getBytes(java.nio.charset.StandardCharsets.US_ASCII))) {
                throw new IllegalStateException("Schema receipt mismatch");
            }
        } catch (Exception error) {
            // Never print a JDBC URL, properties, credentials, or exception text.
            String state = error instanceof SQLException ? " SQLSTATE=" + ((SQLException) error).getSQLState() : "";
            System.err.println("DSpace schema guard refused startup (" + error.getClass().getSimpleName() + state +
                               "). Use the explicit installation/migration recovery procedure.");
            System.exit(78);
        }
    }
}
