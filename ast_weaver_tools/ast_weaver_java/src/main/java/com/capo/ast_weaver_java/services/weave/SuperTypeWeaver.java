package com.capo.ast_weaver_java.services.weave;

import com.github.javaparser.ast.NodeList;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.EnumDeclaration;
import com.github.javaparser.ast.body.RecordDeclaration;
import com.github.javaparser.ast.body.TypeDeclaration;
import com.github.javaparser.ast.type.ClassOrInterfaceType;

import java.util.List;

/**
 * Applies the payload's supertype clauses to the owner type: the frozen tests decide that
 * an adapter IS-A its port ({@code isInstanceOf(TelemetryStreamGateway.class)}), and only
 * this stage can put that clause on the class header. Strictly additive - an existing
 * clause is never removed and identity compares the simple name, so re-weaving converges
 * instead of duplicating.
 */
public final class SuperTypeWeaver {

    private static final String DEFAULT_EXCEPTION_PARENT = "RuntimeException";

    private SuperTypeWeaver() {
    }

    public static void apply(TypeDeclaration<?> owner, String extendsType, List<String> implementsTypes) {
        if (owner instanceof ClassOrInterfaceDeclaration type) {
            applyExtended(type, extendsType);
            for (String supertype : implementsTypes) {
                if (supertype.isBlank()) {
                    continue;
                }
                // Interfaces spell their supertypes as extends; classes as implements.
                if (type.isInterface()) {
                    addIfAbsent(type.getExtendedTypes(), supertype, type::addExtendedType);
                } else {
                    addIfAbsent(type.getImplementedTypes(), supertype, type::addImplementedType);
                }
            }
        } else if (owner instanceof RecordDeclaration record) {
            for (String iface : implementsTypes) {
                if (!iface.isBlank()) {
                    addIfAbsent(record.getImplementedTypes(), iface, record::addImplementedType);
                }
            }
        } else if (owner instanceof EnumDeclaration enumType) {
            for (String iface : implementsTypes) {
                if (!iface.isBlank()) {
                    addIfAbsent(enumType.getImplementedTypes(), iface, enumType::addImplementedType);
                }
            }
        }
    }

    /**
     * The payload's declared parent replaces ONLY the placeholder the exception shell added;
     * a class that already extends a real (non-placeholder) parent keeps it - replacing a
     * peer-visible supertype is nobody's business but its owner unit's green contract.
     */
    private static void applyExtended(ClassOrInterfaceDeclaration type, String extendsType) {
        if (extendsType.isBlank() || type.isInterface()) {
            return;
        }
        NodeList<ClassOrInterfaceType> current = type.getExtendedTypes();
        boolean onlyPlaceholder = current.stream()
            .allMatch(entry -> DEFAULT_EXCEPTION_PARENT.equals(entry.getNameAsString()));
        if (current.isEmpty() || onlyPlaceholder) {
            current.clear();
            type.addExtendedType(extendsType);
            return;
        }
        addIfAbsent(current, extendsType, type::addExtendedType);
    }

    private static void addIfAbsent(NodeList<ClassOrInterfaceType> clauses, String name,
            java.util.function.Consumer<String> adder) {
        String tail = simpleName(name);
        for (ClassOrInterfaceType clause : clauses) {
            if (simpleName(clause.getNameAsString()).equals(tail)) {
                return;
            }
        }
        adder.accept(name);
    }

    private static String simpleName(String name) {
        String bare = name;
        int generic = bare.indexOf('<');
        if (generic > 0) {
            bare = bare.substring(0, generic);
        }
        int dot = bare.lastIndexOf('.');
        return dot >= 0 ? bare.substring(dot + 1) : bare;
    }
}
