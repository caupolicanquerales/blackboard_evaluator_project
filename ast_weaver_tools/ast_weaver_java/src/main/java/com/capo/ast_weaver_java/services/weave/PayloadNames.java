package com.capo.ast_weaver_java.services.weave;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Derives the weaving coordinates - declared kind, simple type name, package - from the
 * payload's export string and the target path. Payload hygiene only: this class never
 * parses Java, it decides where and as what the payload lands.
 */
public final class PayloadNames {

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
        String head = headOf(export);
        String name = head.substring(head.lastIndexOf('.') + 1).trim();
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
     * The export's declared type parameters, e.g. {@code com.x.Box<T>} yields {@code [T]} and
     * {@code Box<K, V extends Comparable<V>>} yields {@code [K, V extends Comparable<V]]}.
     * Empty when the export declares none. Commas inside nested bounds never split.
     */
    public static List<String> typeParameters(String export) {
        int open = export.indexOf('<');
        if (open < 0) {
            return List.of();
        }
        int depth = 0;
        int close = -1;
        for (int i = open; i < export.length(); i++) {
            char c = export.charAt(i);
            if (c == '<') {
                depth++;
            } else if (c == '>' && --depth == 0) {
                close = i;
                break;
            }
        }
        if (close < 0) {
            throw new IllegalStateException("Unbalanced type parameters in export: " + export);
        }
        List<String> params = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        int nesting = 0;
        for (char c : export.substring(open + 1, close).toCharArray()) {
            if (c == '<') {
                nesting++;
            } else if (c == '>') {
                nesting--;
            }
            if (c == ',' && nesting == 0) {
                params.add(current.toString().trim());
                current.setLength(0);
            } else {
                current.append(c);
            }
        }
        if (!current.isEmpty()) {
            params.add(current.toString().trim());
        }
        for (String param : params) {
            if (!param.matches("[A-Za-z_$][\\w$]*(\\s+extends\\s+.+)?")) {
                throw new IllegalStateException("Cannot parse type parameter from export: " + export);
            }
        }
        return params;
    }

    /**
     * The package a new file declares: the export's qualifier when it has one, otherwise
     * the directory chain below the FIRST Maven/Gradle-style source root of the target
     * path ({@code src/<config>/java} - main, test, integration-test alike).
     * (seed-002 2026-11-16: the marker was hardcoded to src/main/java, so a created
     * support class under src/test/java landed WITHOUT a package; the frozen E2E test
     * importing it died on 'duplicate class'/'cannot access' and the whole domain could
     * not go green while the tool reported every splice applied.)
     */
    public static String packageOf(String export, Path targetPath) {
        String head = headOf(export);
        int dot = head.lastIndexOf('.');
        if (dot > 0) {
            return head.substring(0, dot);
        }
        String normalized = targetPath.toAbsolutePath().normalize().toString().replace('\\', '/');
        java.util.regex.Matcher m = SOURCE_ROOT.matcher(normalized);
        if (!m.find()) {
            return "";
        }
        String inside = normalized.substring(m.end());
        int lastSlash = inside.lastIndexOf('/');
        return lastSlash < 0 ? "" : inside.substring(0, lastSlash).replace('/', '.');
    }

    private static final java.util.regex.Pattern SOURCE_ROOT =
            java.util.regex.Pattern.compile("(?:^|/)src/[^/]+/java/");

    /** The export cut before any type-parameter clause, so dots inside bounds never leak. */
    private static String headOf(String export) {
        int open = export.indexOf('<');
        return open > 0 ? export.substring(0, open) : export;
    }
}
