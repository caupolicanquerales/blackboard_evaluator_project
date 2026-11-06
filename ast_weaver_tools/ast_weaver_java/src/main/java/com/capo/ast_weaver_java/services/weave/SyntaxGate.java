package com.capo.ast_weaver_java.services.weave;

import com.sun.source.util.JavacTask;

import javax.tools.Diagnostic;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.SimpleJavaFileObject;
import javax.tools.ToolProvider;
import java.io.IOException;
import java.io.StringWriter;
import java.net.URI;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * The JDK's own parser, in memory and parse-only: every syntax question about the
 * rendered file is answered by the language's final authority, with line numbers, before
 * anything is written. Unresolved types are irrelevant at this stage, which is what lets
 * the gate run without any project classpath. Structural duplicates are the merging
 * stages' job - this is the syntax net below them.
 */
public final class SyntaxGate {

    private static JavaCompiler compiler;

    private SyntaxGate() {
    }

    /** The file's syntax errors as {@code "line N: message"}; empty when it parses. */
    public static synchronized List<String> problems(String source) {
        if (compiler == null) {
            compiler = ToolProvider.getSystemJavaCompiler();
        }
        if (compiler == null) {
            return List.of();
        }
        List<Diagnostic<? extends JavaFileObject>> diagnostics = new ArrayList<>();
        try {
            JavaCompiler.CompilationTask task = compiler.getTask(new StringWriter(), null,
                diagnostics::add, List.of("-proc:none"), List.of(), List.of(new InMemorySource(source)));
            ((JavacTask) task).parse();
        } catch (RuntimeException | IOException unusableGate) {
            return List.of();
        }
        List<String> problems = new ArrayList<>();
        for (Diagnostic<? extends JavaFileObject> diagnostic : diagnostics) {
            if (diagnostic.getKind() == Diagnostic.Kind.ERROR) {
                problems.add("line " + diagnostic.getLineNumber() + ": "
                    + diagnostic.getMessage(Locale.ROOT));
            }
        }
        return problems;
    }

    private static final class InMemorySource extends SimpleJavaFileObject {

        private final String code;

        InMemorySource(String code) {
            super(URI.create("mem:///WeaveGate.java"), Kind.SOURCE);
            this.code = code;
        }

        @Override
        public CharSequence getCharContent(boolean ignoreEncodingErrors) {
            return code;
        }
    }
}
