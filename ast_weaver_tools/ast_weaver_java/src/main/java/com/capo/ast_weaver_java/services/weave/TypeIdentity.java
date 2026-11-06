package com.capo.ast_weaver_java.services.weave;

import com.github.javaparser.ast.type.Type;

/**
 * Type-name comparison the way the overload rules see it: whitespace-insensitive, and
 * qualified spellings equal to their simple names ({@code java.util.List} == {@code List}).
 * Used both for member identity keys and for matching a payload signature against the
 * methods an owner already declares.
 */
public final class TypeIdentity {

    private TypeIdentity() {
    }

    public static boolean same(Type actual, Type expected) {
        String actualText = normalized(actual.asString());
        String expectedText = normalized(expected.asString());
        return actualText.equals(expectedText)
            || simpleText(actualText).equals(simpleText(expectedText));
    }

    /** The identity form of a printed type: normalized and reduced to simple names. */
    public static String key(String typeText) {
        return simpleText(normalized(typeText));
    }

    static String normalized(String type) {
        return type.replaceAll("\\s+", "");
    }

    static String simpleText(String type) {
        return type
            .replace("...", "[]")
            .replaceAll("(?<=\\W|^)(?:[A-Za-z_$][\\w$]*\\.)+(?=[A-Z_$])", "");
    }
}
