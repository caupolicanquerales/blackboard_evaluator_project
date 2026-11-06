package com.capo.ast_weaver_java.services.weave;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.Modifier;
import com.github.javaparser.ast.NodeList;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.EnumDeclaration;
import com.github.javaparser.ast.body.RecordDeclaration;
import com.github.javaparser.ast.body.TypeDeclaration;

/**
 * Creates the public type shells the weaver fills: an entire compilation unit for a new
 * file, or a lone declaration for a loaded file whose payload type is missing. Built as
 * AST - payload text is never concatenated into source.
 */
public final class TypeSkeletons {

    private TypeSkeletons() {
    }

    public static CompilationUnit create(String kind, String type, String pkg) {
        CompilationUnit cu = pkg.isBlank() ? new CompilationUnit() : new CompilationUnit(pkg);
        cu.addType(shell(kind, type));
        return cu;
    }

    public static TypeDeclaration<?> shell(String kind, String type) {
        NodeList<Modifier> publicModifier = new NodeList<>(Modifier.publicModifier());
        return switch (kind) {
            case "interface" -> new ClassOrInterfaceDeclaration(publicModifier, true, type);
            case "enum" -> new EnumDeclaration(publicModifier, type);
            case "record" -> new RecordDeclaration(publicModifier, type);
            default -> {
                ClassOrInterfaceDeclaration created =
                    new ClassOrInterfaceDeclaration(publicModifier, false, type);
                if ("exception".equals(kind)) {
                    created.addExtendedType("RuntimeException");
                }
                yield created;
            }
        };
    }
}
