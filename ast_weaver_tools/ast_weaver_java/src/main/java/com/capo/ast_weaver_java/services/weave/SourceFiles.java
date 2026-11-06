package com.capo.ast_weaver_java.services.weave;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.printer.lexicalpreservation.LexicalPreservingPrinter;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/**
 * The file boundary of the weave: load with lexical preservation, render, run the
 * {@link SyntaxGate} before anything touches the disk, and write only on change.
 * If lexical preservation produced text that no longer parses (its known weakness around
 * inserted nodes), the clean printer gets a chance to rescue the write; only when both
 * fail is the weave refused - with the compiler's own diagnostics.
 */
public final class SourceFiles {

    private SourceFiles() {
    }

    public static CompilationUnit loadExisting(Path targetPath) throws IOException {
        CompilationUnit cu = PayloadParser.compilationUnit(targetPath);
        LexicalPreservingPrinter.setup(cu);
        return cu;
    }

    public static void writeValidated(Path targetPath, CompilationUnit cu, boolean newFile)
            throws IOException {
        String rendered = render(cu, newFile);
        List<String> problems = SyntaxGate.problems(rendered);
        if (!problems.isEmpty() && !newFile) {
            String plain = cu.toString();
            List<String> plainProblems = SyntaxGate.problems(plain);
            if (plainProblems.isEmpty()) {
                rendered = plain;
                problems = plainProblems;
            }
        }
        if (!problems.isEmpty()) {
            throw new IllegalArgumentException("Rendered source does not parse: "
                + String.join("; ", problems));
        }
        writeIfChanged(targetPath, rendered);
    }

    private static String render(CompilationUnit cu, boolean newFile) {
        if (newFile) {
            return cu.toString();
        }
        try {
            return LexicalPreservingPrinter.print(cu);
        } catch (RuntimeException ex) {
            return cu.toString();
        }
    }

    private static void writeIfChanged(Path targetPath, String rendered) throws IOException {
        if (Files.isRegularFile(targetPath) && Files.readString(targetPath).equals(rendered)) {
            return;
        }
        Files.createDirectories(targetPath.getParent());
        Files.writeString(targetPath, rendered);
    }
}
