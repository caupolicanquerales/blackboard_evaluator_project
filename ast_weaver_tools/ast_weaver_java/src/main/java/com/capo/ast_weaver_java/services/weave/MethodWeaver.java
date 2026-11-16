package com.capo.ast_weaver_java.services.weave;

import com.capo.ast_weaver_java.records.CoderChangesPayload;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.NodeList;
import com.github.javaparser.ast.body.CallableDeclaration;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.Parameter;
import com.github.javaparser.ast.body.BodyDeclaration;
import com.github.javaparser.ast.body.CompactConstructorDeclaration;
import com.github.javaparser.ast.body.RecordDeclaration;
import com.github.javaparser.ast.body.TypeDeclaration;

import java.util.List;
import java.util.Optional;

/**
 * Resolves the payload's target method inside the owner and creates it when absent.
 * Overloads are disambiguated by the AST parameter model; an unresolvable overload choice
 * is reported as ambiguity rather than guessed, and a missing method is created from the
 * payload signature through the grammar gateway.
 */
public final class MethodWeaver {

    /** A constructor body that assigns components (`this.x = ...`, optionally guarded). */
    private static final java.util.regex.Pattern ASSIGNS_COMPONENT =
        java.util.regex.Pattern.compile("this\\.\\w+\\s*=[^=]");

    private MethodWeaver() {
    }

    /** The method the payload's body belongs to: matched, or created from the signature. */
    public static MethodDeclaration selectOrCreate(TypeDeclaration<?> owner, CoderChangesPayload payload) {
        List<MethodDeclaration> candidates = owner.getMethodsByName(payload.method());
        Optional<List<Parameter>> expectedParams = PayloadParser.signatureParameters(payload.signature());        if (!candidates.isEmpty() && expectedParams.isEmpty() && candidates.size() == 1) {
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

    /**
     * True when the payload's METHOD name equals its class name: that payload declares a
     * CONSTRUCTOR. Splicing it as a MethodDeclaration would produce `public Foo Foo(...)`
     * - a method that can never assign final fields - so a CORRECT constructor payload
     * would be un-weavable forever and every attempt would charge the coder for the
     * weaver's own shape (observed live: the ReorderWindow storm, 2026-11-12).
     * The same trap exists for RECORDS, where a method-shaped compact constructor
     * (`public void Foo(...)`) is legal Java that NEVER RUNS - silently dead invariants
     * (observed live 2026-11-16: six records shipped guardless because the weaver
     * synthesized `public void <Type>(...)` for every compact-constructor payload).
     */
    public static boolean declaresConstructor(String methodName, TypeDeclaration<?> owner) {
        if (methodName == null || owner == null) {
            return false;
        }
        if (owner instanceof ClassOrInterfaceDeclaration cls) {
            return !cls.isInterface() && methodName.equals(cls.getNameAsString());
        }
        return methodName.equals(owner.getNameAsString());
    }

    /** Select the constructor with matching parameters, or create it (public, bare body).
     *  Returns a BodyDeclaration because a record's compact constructor is modeled by
     *  JavaParser as its own node type, not a CallableDeclaration. */
    public static BodyDeclaration<?> selectOrCreateConstructor(TypeDeclaration<?> owner,
            CoderChangesPayload payload) {
        if (owner instanceof RecordDeclaration record
                && !ASSIGNS_COMPONENT.matcher(
                    payload.body() == null ? "" : payload.body()).find()) {
            // A record guard that never assigns `this.x =` is the COMPACT form (the
            // compiler assigns the components itself). A body that DOES assign them is
            // an explicit CANONICAL constructor - legal in records only when it assigns
            // every component, which is exactly what such payloads do - so it must take
            // the generic path below, not the compact wrap (2026-11-16: wrapping a
            // canonical body into a compact form produced 'cannot assign a value to
            // final variable' and burned three attempts on the tool's own mistake).
            record.getMembers().stream()
                .filter(CompactConstructorDeclaration.class::isInstance)
                .toList()
                .forEach(record.getMembers()::remove);
            String body = payload.body() == null ? "" : payload.body().trim();
            List<BodyDeclaration<?>> parsed = PayloadParser.member(
                record.getNameAsString() + " { " + body + " }", "record",
                record.getNameAsString());
            BodyDeclaration<?> node = parsed.get(0);
            record.addMember(node);
            return node;
        }
        List<Parameter> expectedParams = PayloadParser.signatureParameters(payload.signature())
            .orElseThrow(() -> new IllegalStateException(
                "Cannot create constructor '%s': payload signature is missing or malformed"
                    .formatted(payload.method())));
        List<ConstructorDeclaration> existing = owner.getMembers().stream()
            .filter(ConstructorDeclaration.class::isInstance)
            .map(ConstructorDeclaration.class::cast)
            .toList();
        for (ConstructorDeclaration ctor : existing) {
            if (parametersMatch(ctor.getParameters(), expectedParams)) {
                return ctor;
            }
        }
        String signature = payload.signature() == null ? "" : payload.signature().trim();
        int paren = signature.indexOf('(');
        String head = paren >= 0 ? signature.substring(paren) : signature;
        String rendered = "public " + owner.getNameAsString() + head + " {}";
        ConstructorDeclaration created;
        try {
            created = (ConstructorDeclaration) StaticJavaParser.parseBodyDeclaration(rendered);
        } catch (RuntimeException ex) {
            throw new IllegalArgumentException("Payload signature does not parse as a constructor: "
                + ParseErrors.firstLineOf(ex.getMessage()), ex);
        }
        owner.addMember(created);
        return created;
    }

    /**
     * For {@code interface} payloads: the declared signature as an abstract method, added
     * when the interface does not declare it yet. Returns the method so annotations can be
     * applied to it, empty when nothing was done.
     */
    public static Optional<MethodDeclaration> addAbstractIfAbsent(TypeDeclaration<?> owner,
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
        String declaration = abstractDeclaration(payload);
        try {
            MethodDeclaration created = PayloadParser.methodDeclaration(declaration);
            owner.addMember(created);
            return Optional.of(created);
        } catch (RuntimeException ex) {
            throw new IllegalArgumentException("Payload signature does not parse as a method declaration: "
                + ParseErrors.firstLineOf(ex.getMessage()), ex);
        }
    }

    private static MethodDeclaration createMethod(TypeDeclaration<?> owner, CoderChangesPayload payload) {
        if (payload.signature() == null || !payload.signature().contains("(")) {
            throw new IllegalStateException("Cannot create method '%s': payload signature is missing or malformed"
                .formatted(payload.method()));
        }
        MethodDeclaration created;
        try {
            created = PayloadParser.methodDeclaration(abstractDeclaration(payload));
        } catch (RuntimeException ex) {
            throw new IllegalArgumentException("Payload signature does not parse as a method declaration: "
                + ParseErrors.firstLineOf(ex.getMessage()), ex);
        }
        reconcileFromSignature(created, payload);
        owner.addMember(created);
        return created;
    }

    /**
     * Carries the payload signature's declaration tokens onto the method: the frozen test
     * may demand a STATIC factory (`Resp.from(record)` referenced from a static context),
     * and an instance method can never satisfy it - without this, no payload re-emit could
     * ever converge (the T2-031 loop). Modifiers are read only in their declaration place
     * (before the return type/name); a bare signature (`from(TelemetryRecord r)` - the
     * abstract-contract spelling) has nothing to carry and changes nothing. The return
     * type, when explicit, is reconciled too.
     */
    public static void reconcileFromSignature(MethodDeclaration target, CoderChangesPayload payload) {
        String signature = payload.signature() == null ? "" : payload.signature().trim();
        int paren = signature.indexOf('(');
        if (paren < 0) {
            return;
        }
        java.util.List<String> tokens = new java.util.ArrayList<>();
        for (String token : signature.substring(0, paren).split("\\s+")) {
            if (!token.isEmpty()) {
                tokens.add(token);
            }
        }
        int index = 0;
        boolean modified = false;
        while (index < tokens.size() - 1
                && tokens.get(index).matches("(public|protected|private|static|final|synchronized)")) {
            String modifier = tokens.get(index);
            switch (modifier) {
                case "static" -> { target.setStatic(true); modified = true; }
                case "final" -> { target.setFinal(true); modified = true; }
                case "synchronized" -> { target.setSynchronized(true); modified = true; }
                default -> { }  // access modifier: JavaParser keeps whatever is set
            }
            index++;
        }
        int namePosition = tokens.size() - 1;
        if (namePosition - index > 0) {
            String returnType = String.join(" ", tokens.subList(index, namePosition));
            if (!returnType.equals(target.getTypeAsString())) {
                try {
                    target.setType(com.github.javaparser.StaticJavaParser.parseType(returnType));
                    modified = true;
                } catch (RuntimeException ignored) {
                    // Unparsable type phrase: leave the type untouched. Creation and the
                    // grammar ladder validate signatures properly; this path only reconciles.
                }
            }
        }
        if (modified) {
            SourceFiles.markReshaped();
        }
    }

    private static String abstractDeclaration(CoderChangesPayload payload) {
        return "public %s %s(%s);".formatted(safeReturnType(payload.returns()),
            payload.method().trim(), PayloadParser.rawParameters(payload.signature()));
    }

    private static String safeReturnType(String returns) {
        return returns == null || returns.isBlank() ? "void" : returns.trim();
    }

    /**
     * The signature written as a COMPLETE declaration (`public static &lt;T&gt; T map(T in)`)
     * rather than the bare contract spelling (`map(T in)`). When the payload ships the full
     * form, the method is REPLACED wholesale - modifiers, method-level type parameters,
     * return type and throws all ride the text, so no language shape needs a new schema
     * field or a reconciliation rule. The bare form keeps the field-by-field path.
     */
    public static java.util.Optional<MethodDeclaration> fullDeclaration(CoderChangesPayload payload) {
        String signature = payload.signature() == null ? "" : payload.signature().trim();
        String bare = payload.method() == null ? "" : payload.method().trim();
        if (signature.isEmpty() || bare.isEmpty() || !signature.contains("(")
                || signature.startsWith(bare + "(")) {
            return java.util.Optional.empty();
        }
        try {
            MethodDeclaration parsed = PayloadParser.methodDeclaration(
                signature.endsWith(";") ? signature : signature + ";");
            if (parsed.getNameAsString().equals(bare)) {
                // The table spells bindings without visibility ("String headerName()") and
                // coders copy them verbatim into `signature`: default them PUBLIC like every
                // other path - package-private is never a table's intent for an API member.
                PayloadParser.defaultPublicVisibility(java.util.List.of(parsed));
                return java.util.Optional.of(parsed);
            }
            return java.util.Optional.empty();
        } catch (RuntimeException ex) {
            return java.util.Optional.empty();
        }
    }

    /** Swap the twin method in place (same name, matching parameters OR same erasure),
     *  or add when none exists. Same erasure IS the same method: javac rejects any other
     *  reading ("name clash ... same erasure"), so a generic rewrite of a concrete twin
     *  replaces it instead of clashing beside it.
     *
     *  The twin node itself is KEPT and re-declared in place: the file prints through
     *  lexical preservation, so replacing nodes loses indentation and any annotation the
     *  payload never mentions - modifying in place carries both. */
    public static MethodDeclaration replaceInPlace(TypeDeclaration<?> owner, MethodDeclaration declaration) {
        for (MethodDeclaration existing : owner.getMethodsByName(declaration.getNameAsString())) {
            if (!parametersMatch(existing, declaration.getParameters()) && !sameErasure(existing, declaration)) {
                continue;
            }
            redeclareInPlace(existing, declaration);
            SourceFiles.markReshaped();
            return existing;
        }
        owner.addMember(declaration);
        return declaration;
    }

    private static void redeclareInPlace(MethodDeclaration target, MethodDeclaration source) {
        target.setModifiers(new NodeList<>(source.getModifiers()));
        target.setTypeParameters(new NodeList<>(source.getTypeParameters()));
        target.setType(source.getType().clone());
        target.setParameters(new NodeList<>(source.getParameters()));
        target.setThrownExceptions(new NodeList<>(source.getThrownExceptions()));
        target.setDefault(source.isDefault());
        source.getAnnotations().forEach(annotation -> {
            boolean alreadyPresent = target.getAnnotations().stream().anyMatch(present ->
                present.getNameAsString().equals(annotation.getNameAsString()));
            if (!alreadyPresent) {
                target.addAnnotation(annotation.clone());
            }
        });
    }

    private static boolean sameErasure(MethodDeclaration existing, MethodDeclaration fresh) {
        List<Parameter> left = existing.getParameters();
        List<Parameter> right = fresh.getParameters();
        if (left.size() != right.size()) {
            return false;
        }
        for (int index = 0; index < left.size(); index++) {
            if (left.get(index).isVarArgs() != right.get(index).isVarArgs()) {
                return false;
            }
            String a = TypeIdentity.key(erased(left.get(index).getTypeAsString(), variableNames(existing)));
            String b = TypeIdentity.key(erased(right.get(index).getTypeAsString(), variableNames(fresh)));
            if (!a.equals(b)) {
                return false;
            }
        }
        return true;
    }

    private static java.util.Set<String> variableNames(MethodDeclaration method) {
        java.util.Set<String> names = new java.util.HashSet<>();
        method.getTypeParameters().forEach(parameter -> names.add(parameter.getNameAsString()));
        return names;
    }

    /** Erasure as javac sees it: generics cut to the raw type, the method's OWN type
     *  variables replaced by their erasure ({@code Object} when unbounded). */
    private static String erased(String type, java.util.Collection<String> ownVariables) {
        String head = type.contains("<") ? type.substring(0, type.indexOf('<')) : type;
        head = head.replaceAll("[\\[\\]]", "").replace("...", "").trim();
        return ownVariables.contains(head) ? "Object" : head;
    }

    private static boolean parametersMatch(MethodDeclaration method, List<Parameter> expectedParams) {
        return parametersMatch(method.getParameters(), expectedParams);
    }

    private static boolean parametersMatch(NodeList<Parameter> actualParams, List<Parameter> expectedParams) {
        if (actualParams.size() != expectedParams.size()) {
            return false;
        }
        for (int i = 0; i < actualParams.size(); i++) {
            Parameter actual = actualParams.get(i);
            Parameter expected = expectedParams.get(i);
            if (actual.isVarArgs() != expected.isVarArgs()
                    || !TypeIdentity.same(actual.getType(), expected.getType())) {
                return false;
            }
        }
        return true;
    }
}
