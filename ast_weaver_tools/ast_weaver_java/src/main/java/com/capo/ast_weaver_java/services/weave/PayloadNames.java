package com.capo.ast_weaver_java.services.weave;

import java.nio.file.Path;
import java.util.Locale;
import java.util.Set;

/**
 * Derives the weaving coordinates - declared kind, simple type name, package - from the
 * payload's export string and the target path. Payload hygiene only: this class never
 * parses Java, it decides where and as what the payload lands.
 */
public final class PayloadNames {

    private static final String JAVA_SOURCE_MARKER = "src/main/java";
    private static final Set<String> KINDS = Set.of("class", "interface", "enum", "record", "exception");

    private PayloadNames() {
    }

    /** The normalized declared kind; empty or null payloads default to {@code class}. */
    public static String normalizeKind(String kind) {
        String value = kind == null || kind.isBlank() ? "class" : kind.trim().toLowerCase(Locale.ROOT);
        if (!KINDS.contains(value)) {
            throw new IllegalArgumentException("Unsupported payload kind: " + kind);
        }
        return value;
    }

    /** The simple type name the payload claims to define, from its qualified export. */
    public static String simpleTypeName(String export) {
        String name = export.substring(export.lastIndexOf('.') + 1).trim();
        int boundary = Math.max(name.indexOf('<'), name.indexOf('$'));
        if (boundary > 0) {
            name = name.substring(0, boundary);
        }
        if (!name.matches("[A-Za-z_$][\\w$]*")) {
            throw new IllegalStateException("Cannot derive a Java type name from export: " + export);
        }
        return name;
    }

    /**
     * The package a new file declares: the export's qualifier when it has one, otherwise
     * the directory chain below {@code src/main/java} of the target path.
     */
    public static String packageOf(String export, Path targetPath) {
        int dot = export.lastIndexOf('.');
        if (dot > 0) {
            return export.substring(0, dot);
        }
        String normalized = targetPath.toAbsolutePath().normalize().toString().replace('\\', '/');
        int marker = normalized.indexOf(JAVA_SOURCE_MARKER + "/");
        if (marker < 0) {
            return "";
        }
        String inside = normalized.substring(marker + JAVA_SOURCE_MARKER.length() + 1);
        int lastSlash = inside.lastIndexOf('/');
        return lastSlash < 0 ? "" : inside.substring(0, lastSlash).replace('/', '.');
    }
}
