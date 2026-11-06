package com.capo.ast_weaver_java.services.weave;

import com.capo.ast_weaver_java.records.CoderChangesPayload;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.Parameter;
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

    private MethodWeaver() {
    }

    /** The method the payload's body belongs to: matched, or created from the signature. */
    public static MethodDeclaration selectOrCreate(TypeDeclaration<?> owner, CoderChangesPayload payload) {
        List<MethodDeclaration> candidates = owner.getMethodsByName(payload.method());
        Optional<List<Parameter>> expectedParams = PayloadParser.signatureParameters(payload.signature());
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
        owner.addMember(created);
        return created;
    }

    private static String abstractDeclaration(CoderChangesPayload payload) {
        return "public %s %s(%s);".formatted(safeReturnType(payload.returns()),
            payload.method().trim(), PayloadParser.rawParameters(payload.signature()));
    }

    private static String safeReturnType(String returns) {
        return returns == null || returns.isBlank() ? "void" : returns.trim();
    }

    private static boolean parametersMatch(MethodDeclaration method, List<Parameter> expectedParams) {
        List<Parameter> actualParams = method.getParameters();
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
