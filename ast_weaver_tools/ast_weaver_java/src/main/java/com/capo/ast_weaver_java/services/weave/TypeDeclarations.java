package com.capo.ast_weaver_java.services.weave;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.BodyDeclaration;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.EnumDeclaration;
import com.github.javaparser.ast.body.RecordDeclaration;
import com.github.javaparser.ast.body.TypeDeclaration;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * Structural views of a type declaration: what kind it really is, everything it declares
 * in javac's reading order, and where the payload's type lives in a compilation unit.
 */
public final class TypeDeclarations {

    private TypeDeclarations() {
    }

    /** The kind a merged owner really is, which is what decides the grammar ladder. */
    public static String kindOf(TypeDeclaration<?> owner) {
        if (owner instanceof RecordDeclaration) {
            return "record";
        }
        if (owner instanceof EnumDeclaration) {
            return "enum";
        }
        if (owner instanceof ClassOrInterfaceDeclaration declared && declared.isInterface()) {
            return "interface";
        }
        return "class";
    }

    /**
     * Every member the owner declares, in the order javac reads them. JavaParser keeps
     * enum constants in a separate {@code getEntries()} list that {@code getMembers()}
     * omits, so identity scans must see both or re-weaving duplicates a constant.
     */
    public static List<BodyDeclaration<?>> all(TypeDeclaration<?> owner) {
        if (owner instanceof EnumDeclaration enumType) {
            List<BodyDeclaration<?>> all = new ArrayList<>(enumType.getEntries());
            all.addAll(enumType.getMembers());
            return all;
        }
        return new ArrayList<>(owner.getMembers());
    }

    /**
     * The payload's type inside a loaded file: top-level declarations win over nested ones;
     * a missing type is created from the same shell the new-file path uses. Returns null
     * for {@code record} payloads whose type is absent - a record's header cannot be woven
     * into a file that does not declare it, so the caller writes what it has (imports).
     */
    public static TypeDeclaration<?> findOrCreate(CompilationUnit cu, String type, String kind) {
        Optional<TypeDeclaration<?>> topLevel = cu.getTypes().stream()
            .filter(candidate -> candidate.getNameAsString().equals(type))
            .findFirst();
        if (topLevel.isPresent()) {
            return topLevel.get();
        }
        for (TypeDeclaration<?> candidate : cu.findAll(TypeDeclaration.class)) {
            if (candidate.getNameAsString().equals(type)) {
                return candidate;
            }
        }
        if ("record".equals(kind)) {
            return null;
        }
        TypeDeclaration<?> created = TypeSkeletons.shell(kind, type);
        cu.addType(created);
        return cu.getType(cu.getTypes().size() - 1);
    }
}
