package com.capo.ast_weaver_java.services;

import com.capo.ast_weaver_java.records.CoderChangesPayload;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.Modifier;
import com.github.javaparser.ast.body.BodyDeclaration;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.Parameter;
import com.github.javaparser.ast.body.RecordDeclaration;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.body.TypeDeclaration;
import com.github.javaparser.ast.nodeTypes.NodeWithAnnotations;
import com.github.javaparser.ast.stmt.BlockStmt;
import com.github.javaparser.ast.type.Type;
import com.github.javaparser.printer.lexicalpreservation.LexicalPreservingPrinter;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

public final class JavaASTWeaver {

    private static final String JAVA_SOURCE_MARKER = "src/main/java";
    private static final Set<String> KINDS = Set.of("class", "interface", "enum", "record", "exception");

    static {
        StaticJavaParser.getParserConfiguration()
            .setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE);
    }

    private JavaASTWeaver() {
    }

    public static void weave(Path targetPath, CoderChangesPayload payload) throws IOException {
        Objects.requireNonNull(targetPath, "targetPath is required");
        Objects.requireNonNull(payload, "payload is required");

        String kind = normalizeKind(payload.kind());
        String simpleTypeName = simpleTypeName(payload.export());
        boolean newFile = !Files.isRegularFile(targetPath);
        boolean createdType = false;

        CompilationUnit cu;
        if (newFile) {
            cu = parseSkeleton(targetPath, payload, kind, simpleTypeName);
            createdType = true;
        } else {
            cu = StaticJavaParser.parse(targetPath);
            LexicalPreservingPrinter.setup(cu);
        }

        addImports(cu, payload.imports());
        TypeDeclaration<?> owner = findOrCreateType(cu, simpleTypeName, kind, payload);
        if (owner == null) {
            writeIfChanged(targetPath, render(cu, createdType));
            return;
        }
        createdType = createdType || addMissingMembers(owner, payload.members());
        applyAnnotations(owner, payload.annotations());

        if (!"interface".equals(kind) && !payload.body().isBlank()) {
            MethodDeclaration target = findOrCreateMethod(owner, payload);
            applyAnnotations(target, payload.methodAnnotations());
            target.setBody(parseMethodBody(payload.body()));
        } else if ("interface".equals(kind)) {
            Optional<MethodDeclaration> declared = addAbstractMethod(owner, payload);
            declared.ifPresent(method -> applyAnnotations(method, payload.methodAnnotations()));
            createdType |= declared.isPresent();
        }

        writeIfChanged(targetPath, render(cu, createdType));
    }

    private static void writeIfChanged(Path targetPath, String rendered) throws IOException {
        if (Files.isRegularFile(targetPath) && Files.readString(targetPath).equals(rendered)) {
            return;
        }
        Files.createDirectories(targetPath.getParent());
        Files.writeString(targetPath, rendered);
    }

    private static String normalizeKind(String kind) {
        String value = kind == null || kind.isBlank() ? "class" : kind.trim().toLowerCase(Locale.ROOT);
        if (!KINDS.contains(value)) {
            throw new IllegalArgumentException("Unsupported payload kind: " + kind);
        }
        return value;
    }

    private static final java.util.regex.Pattern RECORD_COMPONENT =
        java.util.regex.Pattern.compile("^(?:final\\s+)?[\\w.$]+(?:<[\\w.$,<>\\[]\\s]*>)?\\s+[\\w$]+$");

    private static CompilationUnit parseSkeleton(Path targetPath, CoderChangesPayload payload,
            String kind, String type) {
        String packageName = packageOf(payload.export(), targetPath);
        List<String> members = terminatedMembers(payload.members());
        String body = switch (kind) {
            case "interface" -> " {\n" + String.join("\n", members) + "\n}";
            case "enum" -> " {\n" + String.join(",\n", members) + ";\n}";
            case "record" -> recordSkeletonBody(payload);
            case "exception" -> " extends RuntimeException {\n" + String.join("\n", members) + "\n}";
            default -> " {\n" + String.join("\n", members) + "\n}";
        };
        String keyword = switch (kind) {
            case "interface" -> "public interface ";
            case "enum" -> "public enum ";
            case "record" -> "public record ";
            default -> "public class ";
        };
        String source = (packageName.isBlank() ? "" : "package %s;\n\n".formatted(packageName))
            + keyword + type + body;
        try {
            return StaticJavaParser.parse(source);
        } catch (RuntimeException ex) {
            throw new IllegalArgumentException("Payload members do not parse inside " + kind + " " + type
                + ": " + firstLineOf(ex.getMessage()) + " | first member: "
                + head(payload.members().isEmpty() ? "(none)" : payload.members().get(0)), ex);
        }
    }

    /**
     * Payload members arrive as text lines, and a field without its ';' is the most common
     * omission. Terminating them here costs nothing and saves the retry session that a parse
     * error would otherwise burn.
     */
    private static List<String> terminatedMembers(List<String> members) {
        List<String> out = new ArrayList<>();
        for (String member : members) {
            if (member == null || member.isBlank()) {
                continue;
            }
            String text = member.trim();
            if (!text.endsWith(";") && !text.endsWith("}") && !text.endsWith("{")
                    && !text.endsWith(")") && !text.endsWith(",")) {
                text = text + ";";
            }
            out.add(text);
        }
        return out;
    }

    private static String head(String text) {
        String line = text.strip().lines().findFirst().orElse("");
        return line.length() <= 80 ? line : line.substring(0, 80) + "...";
    }

    /**
     * Record header components and record body members are different things, and the coder
     * payload carries both in `members`. Pasting every entry into the header makes any compact
     * constructor or extra method a parse error, so the entry is routed by shape: a bare
     * `Type name` becomes a component and anything else stays a body member.
     */
    private static String recordSkeletonBody(CoderChangesPayload payload) {
        List<String> components = new ArrayList<>();
        List<String> members = new ArrayList<>();
        for (String entry : payload.members()) {
            if (entry == null || entry.isBlank()) {
                continue;
            }
            String component = recordComponentOf(entry.trim());
            if (component == null) {
                String text = entry.trim();
                members.add(text.endsWith("}") || text.endsWith(";") ? text : text + ";");
            } else {
                components.add(component);
            }
        }
        String header = "(" + String.join(", ", components) + ")";
        return members.isEmpty() ? header + " {\n}" : header + " {\n" + String.join("\n", members) + "\n}";
    }

    /** A record component is a bare `Type name`; anything else is a body member. */
    private static String recordComponentOf(String entry) {
        String stripped = (entry.endsWith(";") ? entry.substring(0, entry.length() - 1) : entry).trim();
        String candidate = stripped.replaceAll("^(?:private|public|protected|static)\\s+", "")
            .replaceAll("^final\\s+", "").trim();
        return RECORD_COMPONENT.matcher(candidate).matches() ? candidate : null;
    }

    private static TypeDeclaration<?> findOrCreateType(CompilationUnit cu, String type,
            String kind, CoderChangesPayload payload) {
        for (TypeDeclaration<?> candidate : cu.findAll(TypeDeclaration.class)) {
            if (candidate.getNameAsString().equals(type)) {
                return candidate;
            }
        }
        if ("record".equals(kind)) {
            return null;
        }
        String source = "interface".equals(kind)
            ? "public interface %s { }".formatted(type)
            : "public class %s { }".formatted(type);
        TypeDeclaration<?> created = StaticJavaParser.parseTypeDeclaration(source);
        cu.addType(created);
        return cu.getType(cu.getTypes().size() - 1);
    }

    private static boolean addMissingMembers(TypeDeclaration<?> owner, List<String> members) {
        if (members.isEmpty()) {
            return false;
        }
        Set<String> present = new java.util.HashSet<>();
        for (BodyDeclaration<?> member : owner.getMembers()) {
            present.add(normalizeCode(member.toString()));
        }
        boolean added = false;
        for (String declaration : terminatedMembers(members)) {
            if (present.contains(normalizeCode(declaration))) {
                continue;
            }
            if (owner instanceof RecordDeclaration && recordComponentOf(declaration) != null) {
                continue;
            }
            for (BodyDeclaration<?> parsed : parseMemberDeclarations(declaration, owner.getNameAsString())) {
                owner.addMember(parsed);
                present.add(normalizeCode(parsed.toString()));
                added = true;
            }
        }
        return added;
    }

    private static List<BodyDeclaration<?>> parseMemberDeclarations(String declaration, String typeName) {
        try {
            return new ArrayList<>(StaticJavaParser
                .parseTypeDeclaration("class WeaverProbe {" + declaration + "\n}")
                .getMembers());
        } catch (RuntimeException classShape) {
            try {
                return new ArrayList<>(StaticJavaParser
                    .parseTypeDeclaration("record WeaverProbe(String component) {" + declaration + "\n}")
                    .getMembers());
            } catch (RuntimeException recordShape) {
                throw new IllegalArgumentException("Payload member does not parse inside " + typeName + ": "
                    + firstLineOf(classShape.getMessage()) + " | member: " + head(declaration), classShape);
            }
        }
    }

    private static Optional<MethodDeclaration> addAbstractMethod(TypeDeclaration<?> owner,
            CoderChangesPayload payload) {
        List<MethodDeclaration> existing = owner.getMethodsByName(payload.method());
        if (!(owner instanceof ClassOrInterfaceDeclaration declared) || !declared.isInterface()) {
            return Optional.empty();
        }
        if (!existing.isEmpty()) {
            return Optional.of(existing.get(0));
        }
        if (payload.signature() == null || !payload.signature().contains("(")) {
            return Optional.empty();
        }
        String declaration = "public %s %s(%s);".formatted(safeReturnType(payload.returns()),
            payload.method().trim(), rawParameters(payload.signature()));
        try {
            MethodDeclaration created = StaticJavaParser.parseMethodDeclaration(declaration);
            owner.addMember(created);
            return Optional.of(created);
        } catch (RuntimeException ex) {
            throw new IllegalArgumentException("Payload signature does not parse as a method declaration: "
                + firstLineOf(ex.getMessage()), ex);
        }
    }

    /**
     * The payload carries the annotations a framework needs (`@RestController`,
     * `@PostMapping("/ingress")`) because a greenfield type is created here: without them the
     * coder has nowhere to put them, and the unit compiles but never gets wired.
     * Existing annotations with the same name are left alone, so re-weaving stays idempotent.
     */
    private static void applyAnnotations(Node target, List<String> annotations) {
        if (!(target instanceof NodeWithAnnotations<?> holder)) {
            return;
        }
        for (String raw : annotations) {
            if (raw == null || raw.isBlank()) {
                continue;
            }
            String text = raw.trim();
            if (text.startsWith("@")) {
                text = text.substring(1);
            }
            String name = text.split("[(\\s]")[0].trim();
            boolean present = holder.getAnnotations().stream()
                .anyMatch(annotation -> annotation.getNameAsString().equals(name));
            if (present || name.isEmpty()) {
                continue;
            }
            try {
                holder.addAnnotation(StaticJavaParser.parseAnnotation("@" + text));
            } catch (RuntimeException ex) {
                throw new IllegalArgumentException("Payload annotation does not parse: " + raw
                    + " (" + firstLineOf(ex.getMessage()) + ")", ex);
            }
        }
    }

    private static String normalizeCode(String code) {
        String collapsed = code.replaceAll("\\s+", " ").trim();
        return collapsed.endsWith(";") ? collapsed.substring(0, collapsed.length() - 1) : collapsed;
    }

    private static String render(CompilationUnit cu, boolean createdNodes) {
        if (createdNodes) {
            return cu.toString();
        }
        try {
            return LexicalPreservingPrinter.print(cu);
        } catch (RuntimeException ex) {
            return cu.toString();
        }
    }

    private static void addImports(CompilationUnit cu, List<String> imports) {
        imports.stream()
            .filter(Objects::nonNull)
            .map(String::trim)
            .filter(importFqn -> !importFqn.isEmpty())
            .filter(importFqn -> !importFqn.startsWith("java.lang."))
            .forEach(cu::addImport);
    }

    private static MethodDeclaration findOrCreateMethod(TypeDeclaration<?> owner,
            CoderChangesPayload payload) {
        List<MethodDeclaration> candidates = owner.getMethodsByName(payload.method());
        Optional<List<Parameter>> expectedParams = parseSignatureParameters(payload.signature());
        if (!candidates.isEmpty() && expectedParams.isEmpty() && candidates.size() == 1) {
            return candidates.get(0);
        }
        if (!candidates.isEmpty() && expectedParams.isPresent()) {
            Optional<MethodDeclaration> matching = candidates.stream()
                .filter(method -> parametersMatch(method, expectedParams.get()))
                .findFirst();
            if (matching.isPresent()) {
                return matching.get();
            }
        }
        if (!candidates.isEmpty() && expectedParams.isEmpty() && candidates.size() > 1) {
            throw new IllegalStateException("Ambiguous overload for '%s': signature required"
                .formatted(payload.method()));
        }
        return createMethod(owner, payload);
    }

    private static MethodDeclaration createMethod(TypeDeclaration<?> owner,
            CoderChangesPayload payload) {
        if (payload.signature() == null || !payload.signature().contains("(")) {
            throw new IllegalStateException("Cannot create method '%s': payload signature is missing or malformed"
                .formatted(payload.method()));
        }
        String declaration = "public %s %s(%s);".formatted(safeReturnType(payload.returns()),
            payload.method().trim(), rawParameters(payload.signature()));
        MethodDeclaration created;
        try {
            created = StaticJavaParser.parseMethodDeclaration(declaration);
        } catch (RuntimeException ex) {
            throw new IllegalArgumentException("Payload signature does not parse as a method declaration: "
                + firstLineOf(ex.getMessage()), ex);
        }
        owner.addMember(created);
        return created;
    }

    private static String safeReturnType(String returns) {
        return returns == null || returns.isBlank() ? "void" : returns.trim();
    }

    private static String rawParameters(String signature) {
        int open = signature.indexOf('(');
        int close = signature.lastIndexOf(')');
        return (open < 0 || close < open) ? "" : signature.substring(open + 1, close).trim();
    }

    private static String packageOf(String export, Path targetPath) {
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

    private static String simpleTypeName(String export) {
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

    private static Optional<List<Parameter>> parseSignatureParameters(String signature) {
        if (signature == null || signature.isBlank()) {
            return Optional.empty();
        }
        int open = signature.indexOf('(');
        int close = signature.lastIndexOf(')');
        if (open < 0 || close < open) {
            return Optional.empty();
        }
        String parameters = signature.substring(open + 1, close).trim();
        if (parameters.isEmpty()) {
            return Optional.of(List.of());
        }
        List<Parameter> parsed = new ArrayList<>();
        for (String declaration : splitTopLevelParameters(parameters)) {
            parsed.add(toParameter(declaration, signature));
        }
        return Optional.of(parsed);
    }

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
            return StaticJavaParser.parseParameter(declaration);
        } catch (RuntimeException typeOnly) {
            try {
                return StaticJavaParser.parseParameter(declaration + " p");
            } catch (RuntimeException malformed) {
                throw new IllegalStateException("Malformed signature: " + signature, malformed);
            }
        }
    }

    private static boolean parametersMatch(MethodDeclaration method, List<Parameter> expectedParams) {
        List<Parameter> actualParams = method.getParameters();
        if (actualParams.size() != expectedParams.size()) {
            return false;
        }
        for (int i = 0; i < actualParams.size(); i++) {
            Parameter actual = actualParams.get(i);
            Parameter expected = expectedParams.get(i);
            if (actual.isVarArgs() != expected.isVarArgs() || !sameType(actual.getType(), expected.getType())) {
                return false;
            }
        }
        return true;
    }

    private static boolean sameType(Type actual, Type expected) {
        String actualText = normalizeType(actual.asString());
        String expectedText = normalizeType(expected.asString());
        return actualText.equals(expectedText)
            || simpleTypeText(actualText).equals(simpleTypeText(expectedText));
    }

    private static String normalizeType(String type) {
        return type.replaceAll("\\s+", "");
    }

    private static String simpleTypeText(String type) {
        return type
            .replace("...", "[]")
            .replaceAll("(?<=\\W|^)(?:[A-Za-z_$][\\w$]*\\.)+(?=[A-Z_$])", "");
    }

    private static BlockStmt parseMethodBody(String body) {
        try {
            return StaticJavaParser.parseBlock("{\n" + body + "\n}");
        } catch (RuntimeException ex) {
            throw new IllegalArgumentException("Coder payload body does not parse as a method body: "
                + firstLineOf(ex.getMessage()), ex);
        }
    }

    private static String firstLineOf(String message) {
        if (message == null || message.isBlank()) {
            return "unknown parse problem";
        }
        int lineEnd = message.indexOf('\n');
        return (lineEnd >= 0 ? message.substring(0, lineEnd) : message).trim();
    }
}
