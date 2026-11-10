package com.capo.ast_weaver_java.services.weave;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.Modifier;
import com.github.javaparser.ast.NodeList;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.EnumDeclaration;
import com.github.javaparser.ast.body.RecordDeclaration;
import com.github.javaparser.ast.body.TypeDeclaration;

import java.util.List;

/**
 * Creates the public type shells the weaver fills: an entire compilation unit for a new
 * file, or a lone declaration for a loaded file whose payload type is missing. Built as
 * AST - payload text is never concatenated into source.
 */
public final class TypeSkeletons {

    private TypeSkeletons() {
    }

    public static CompilationUnit create(String kind, String type, List<String> typeParameters, String pkg) {
        CompilationUnit cu = pkg.isBlank() ? new CompilationUnit() : new CompilationUnit(pkg);
        cu.addType(shell(kind, type, typeParameters));
        return cu;
    }

    public static TypeDeclaration<?> shell(String kind, String type, List<String> typeParameters) {
        NodeList<Modifier> publicModifier = new NodeList<>(Modifier.publicModifier());
        return switch (kind) {
            case "interface" -> {
                ClassOrInterfaceDeclaration created =
                    new ClassOrInterfaceDeclaration(publicModifier, true, type);
                declareParameters(created, typeParameters);
                yield created;
            }
            // enums cannot be generic (JLS 8.9); a record's parameters ride its header text.
            case "enum" -> new EnumDeclaration(publicModifier, type);
            case "record" -> new RecordDeclaration(publicModifier, type);
            default -> {
                ClassOrInterfaceDeclaration created =
                    new ClassOrInterfaceDeclaration(publicModifier, false, type);
                if ("exception".equals(kind)) {
                    created.addExtendedType("RuntimeException");
                }
                declareParameters(created, typeParameters);
                yield created;
            }
        };
    }

    /** The payload's declared generics, kept: a shell named {@code Box<T>} must BE generic. */
    private static void declareParameters(ClassOrInterfaceDeclaration created, List<String> typeParameters) {
        for (String parameter : typeParameters) {
            if (!parameter.isBlank()) {
                created.addTypeParameter(parameter);
            }
        }
    }
}
