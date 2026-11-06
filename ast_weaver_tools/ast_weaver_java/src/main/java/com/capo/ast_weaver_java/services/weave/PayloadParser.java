package com.capo.ast_weaver_java.services.weave;

import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.BodyDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.Parameter;
import com.github.javaparser.ast.body.TypeDeclaration;
import com.github.javaparser.ast.expr.AnnotationExpr;
import com.github.javaparser.ast.stmt.BlockStmt;

import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.function.Supplier;

/**
 * The grammar gateway: the only class in the weaver that touches the JavaParser facade,
 * and the only place (besides {@link MemberIdentity}) that knows how payload text becomes
 * AST nodes. Owns the language level and the member-context ladder:
 * <ol>
 *   <li>a member as written,</li>
 *   <li>a member whose missing terminator is supplied,</li>
 *   <li>the owner-specific context a member can only parse inside (compact constructors in
 *       a record, enum constants in an enum),</li>
 *   <li>a whole class body, for one entry carrying several declarations.</li>
 * </ol>
 * No rung pattern-matches text; a legal Java shape is accepted by some grammar context or
 * the error names the member and every rung that rejected it. New shapes never need a new
 * rung - only a genuinely new JLS member context does.
 */
public final class PayloadParser {

    static {
        StaticJavaParser.getParserConfiguration()
            .setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE);
    }

    private PayloadParser() {
    }

    // --- whole-source entry points ---

    public static CompilationUnit compilationUnit(Path file) throws IOException {
        return StaticJavaParser.parse(file);
    }

    // --- the member ladder ---

    public static List<BodyDeclaration<?>> members(List<String> rawMembers, String ladderKind,
            String holderType) {
        List<BodyDeclaration<?>> out = new ArrayList<>();
        for (String member : rawMembers) {
            if (member != null && !member.isBlank()) {
                out.addAll(member(member.trim(), ladderKind, holderType));
            }
        }
        return out;
    }

    public static List<BodyDeclaration<?>> member(String text, String ladderKind, String holderType) {
        String holder = holderType == null || holderType.isBlank() ? "WeaverProbe" : holderType;
        List<String> errors = new ArrayList<>();

        List<BodyDeclaration<?>> parsed = attempt(errors, "member",
            () -> List.of(StaticJavaParser.parseBodyDeclaration(text)));
        if (parsed != null) {
            return parsed;
        }
        if (mayNeedTerminator(text)) {
            parsed = attempt(errors, "member with ';' appended",
                () -> List.of(StaticJavaParser.parseBodyDeclaration(text + ";")));
            if (parsed != null) {
                return parsed;
            }
        }
        if ("record".equals(ladderKind)) {
            parsed = attempt(errors, "record body",
                () -> probeMembers("record " + holder + "(String __weaverComponent) {\n" + text + "\n}", holder));
            if (parsed != null && !parsed.isEmpty()) {
                return parsed;
            }
        }
        if ("enum".equals(ladderKind)) {
            parsed = attempt(errors, "enum body",
                () -> probeMembers("enum " + holder + " {\n" + text + "\n}", holder));
            if (parsed != null && !parsed.isEmpty()) {
                return parsed;
            }
        }
        parsed = attempt(errors, "class body",
            () -> probeMembers("class " + holder + " {\n" + text + "\n}", holder));
        if (parsed != null && !parsed.isEmpty()) {
            return parsed;
        }
        throw new IllegalArgumentException("Payload member does not parse inside " + holder + ": "
            + String.join(" || ", errors) + " | member: " + ParseErrors.head(text));
    }

    // --- single-node grammar entry points used by the merging stages ---

    public static Parameter parameter(String declaration) {
        return StaticJavaParser.parseParameter(declaration);
    }

    public static MethodDeclaration methodDeclaration(String declaration) {
        return StaticJavaParser.parseMethodDeclaration(declaration);
    }

    public static TypeDeclaration<?> typeDeclaration(String declaration) {
        return StaticJavaParser.parseTypeDeclaration(declaration);
    }

    public static AnnotationExpr annotation(String text) {
        return StaticJavaParser.parseAnnotation("@" + text);
    }

    public static BlockStmt body(String text) {
        try {
            return StaticJavaParser.parseBlock("{\n" + text + "\n}");
        } catch (RuntimeException ex) {
            throw new IllegalArgumentException("Coder payload body does not parse as a method body: "
                + ParseErrors.firstLineOf(ex.getMessage()), ex);
        }
    }

    // --- signature realm ---

    /** The text between the parentheses of a payload signature, e.g. {@code "double rate"}. */
    public static String rawParameters(String signature) {
        int open = signature.indexOf('(');
        int close = signature.lastIndexOf(')');
        return (open < 0 || close < open) ? "" : signature.substring(open + 1, close).trim();
    }

    /**
     * The payload's signature parameters, through the grammar first (one wrapper
     * declaration does the whole split, annotations and generics included), with the
     * legacy splitter kept only as a fallback for type-only parameter lists.
     */
    public static Optional<List<Parameter>> signatureParameters(String signature) {
        if (signature == null || signature.isBlank()) {
            return Optional.empty();
        }
        String parameters = rawParameters(signature);
        if (parameters.isEmpty()) {
            return Optional.of(List.of());
        }
        try {
            MethodDeclaration probe = methodDeclaration("public void __weaverProbe__(" + parameters + ");");
            return Optional.of(new ArrayList<>(probe.getParameters()));
        } catch (RuntimeException grammar) {
            // fall through: the legacy path knows `calculateTax(String)` style lists
        }
        List<Parameter> parsed = new ArrayList<>();
        for (String declaration : splitTopLevelParameters(parameters)) {
            parsed.add(toParameter(declaration, signature));
        }
        return Optional.of(parsed);
    }

    // --- ladder internals ---

    private static List<BodyDeclaration<?>> probeMembers(String source, String holder) {
        List<BodyDeclaration<?>> found = new ArrayList<>();
        StaticJavaParser.parse(source).findAll(TypeDeclaration.class).stream()
            .filter(type -> type.getNameAsString().equals(holder))
            .findFirst()
            .ifPresent(type -> found.addAll(TypeDeclarations.all(type)));
        return found;
    }

    private static List<BodyDeclaration<?>> attempt(List<String> errors, String rung,
            Supplier<List<BodyDeclaration<?>>> parse) {
        try {
            return parse.get();
        } catch (RuntimeException ex) {
            String line = ParseErrors.firstLineOf(ex.getMessage());
            if (line.length() > 160) {
                line = line.substring(0, 160) + "...";
            }
            errors.add(rung + ": " + line);
            return null;
        }
    }

    private static boolean mayNeedTerminator(String text) {
        return !text.endsWith(";") && !text.endsWith("}") && !text.endsWith("{")
            && !text.endsWith(")") && !text.endsWith(",");
    }

    /** Fallback split for parameter lists the grammar wrapper rejects. */
    private static List<String> splitTopLevelParameters(String parameters) {
        List<String> parts = new ArrayList<>();
        int depth = 0;
        int start = 0;
        for (int i = 0; i < parameters.length(); i++) {
            char c = parameters.charAt(i);
            if (c == '(' || c == '<' || c == '[') {
                depth++;
            } else if (c == ')' || c == '>' || c == ']') {
                depth--;
            } else if (c == ',' && depth == 0) {
                parts.add(parameters.substring(start, i).trim());
                start = i + 1;
            }
        }
        parts.add(parameters.substring(start).trim());
        return parts;
    }

    private static Parameter toParameter(String declaration, String signature) {
        try {
            return parameter(declaration);
        } catch (RuntimeException typeOnly) {
            try {
                return parameter(declaration + " p");
            } catch (RuntimeException malformed) {
                throw new IllegalStateException("Malformed signature: " + signature, malformed);
            }
        }
    }
}
