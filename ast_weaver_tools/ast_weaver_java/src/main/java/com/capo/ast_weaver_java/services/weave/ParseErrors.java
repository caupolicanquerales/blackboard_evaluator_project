package com.capo.ast_weaver_java.services.weave;

/**
 * Formats grammar failures into the payload-facing messages the retry loop reads:
 * the compiler's first line, and a bounded preview of the offending fragment.
 */
public final class ParseErrors {

    private static final int HEAD_LIMIT = 80;

    private ParseErrors() {
    }

    public static String firstLineOf(String message) {
        if (message == null || message.isBlank()) {
            return "unknown parse problem";
        }
        int lineEnd = message.indexOf('\n');
        return (lineEnd >= 0 ? message.substring(0, lineEnd) : message).trim();
    }

    public static String head(String text) {
        String line = text.strip().lines().findFirst().orElse("");
        return line.length() <= HEAD_LIMIT ? line : line.substring(0, HEAD_LIMIT) + "...";
    }
}
