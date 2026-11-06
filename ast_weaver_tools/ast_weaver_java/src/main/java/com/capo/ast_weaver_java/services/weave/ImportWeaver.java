package com.capo.ast_weaver_java.services.weave;

import com.github.javaparser.ast.CompilationUnit;

import java.util.List;
import java.util.Objects;

/**
 * Adds the payload's imports, skipping {@code java.lang} and whatever the compilation
 * unit already declares.
 */
public final class ImportWeaver {

    private ImportWeaver() {
    }

    public static void apply(CompilationUnit cu, List<String> imports) {
        imports.stream()
            .filter(Objects::nonNull)
            .map(String::trim)
            .filter(importFqn -> !importFqn.isEmpty())
            .filter(importFqn -> !importFqn.startsWith("java.lang."))
            .forEach(cu::addImport);
    }
}
