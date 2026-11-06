package com.capo.ast_weaver_java.services.weave;

import com.github.javaparser.ast.body.BodyDeclaration;
import com.github.javaparser.ast.body.CompactConstructorDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.EnumConstantDeclaration;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.Parameter;
import com.github.javaparser.ast.body.TypeDeclaration;

import java.util.ArrayList;
import java.util.List;

/**
 * What makes two members the same member, decided on the AST's own signature model -
 * never on printed text. Re-weaving replaces the twin a key finds; appending a second
 * member with an identical key is the "already defined" bug class this closes.
 *
 * <p>Compact constructors get their own key because JavaParser models them as their own
 * node type ({@code CompactConstructorDeclaration} is not a {@code ConstructorDeclaration})
 * and a record legally declares at most one.
 */
public final class MemberIdentity {

    private MemberIdentity() {
    }

    /** Null means "no identity rule"; callers fall back to text equality. */
    public static String keyOf(BodyDeclaration<?> member) {
        if (member instanceof CompactConstructorDeclaration) {
            return "compact-ctor()";
        }
        if (member instanceof ConstructorDeclaration ctor) {
            return "ctor(" + paramKey(ctor.getParameters()) + ")";
        }
        if (member instanceof MethodDeclaration method) {
            return method.getNameAsString() + "(" + paramKey(method.getParameters()) + ")";
        }
        if (member instanceof EnumConstantDeclaration constant) {
            return "enum-const " + constant.getNameAsString();
        }
        if (member instanceof TypeDeclaration<?> type) {
            return "type " + type.getNameAsString();
        }
        if (member instanceof FieldDeclaration field) {
            List<String> names = new ArrayList<>();
            field.getVariables().forEach(variable -> names.add(variable.getNameAsString()));
            return "field " + String.join(",", names);
        }
        return null;
    }

    public static String paramKey(List<Parameter> parameters) {
        List<String> keys = new ArrayList<>();
        for (Parameter parameter : parameters) {
            keys.add(TypeIdentity.key(parameter.getType().asString())
                + (parameter.isVarArgs() ? "..." : ""));
        }
        return String.join(",", keys);
    }

    /** Collapsed text used only when no key rule applies (initializers). */
    public static String normalizeCode(String code) {
        String collapsed = code.replaceAll("\\s+", " ").trim();
        return collapsed.endsWith(";") ? collapsed.substring(0, collapsed.length() - 1) : collapsed;
    }
}
