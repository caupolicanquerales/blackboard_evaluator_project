package com.capo.ast_weaver_java.services.weave;

import com.github.javaparser.ast.AccessSpecifier;
import com.github.javaparser.ast.Modifier;
import com.github.javaparser.ast.body.BodyDeclaration;
import com.github.javaparser.ast.body.CompactConstructorDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.EnumDeclaration;
import com.github.javaparser.ast.body.RecordDeclaration;
import com.github.javaparser.ast.body.TypeDeclaration;
import com.github.javaparser.ast.nodeTypes.NodeWithModifiers;

/**
 * JLS rules the payloads routinely violate, normalized as AST operations - never as text
 * edits. Each rule here exists because coder models write the syntax javac forbids; a new
 * incident of this kind is one small rule, not a new patch across the weaver.
 */
public final class SemanticFixups {

    private SemanticFixups() {
    }

    /**
     * Constructor access is grammar-constrained by the owner kind:
     * <ul>
     *   <li>JLS 8.10.3/8.10.4: a record's canonical and compact constructors must carry
     *       the record's own access - javac answers "invalid canonical constructor".</li>
     *   <li>JLS 8.9.1: an enum constructor must not be public or protected - javac
     *       answers "an enum constructor cannot be public".</li>
     * </ul>
     */
    public static void enforceConstructorAccess(TypeDeclaration<?> owner) {
        if (owner instanceof RecordDeclaration record) {
            String canonicalKey = MemberIdentity.paramKey(record.getParameters());
            for (BodyDeclaration<?> member : record.getMembers()) {
                boolean canonical = member instanceof CompactConstructorDeclaration
                    || (member instanceof ConstructorDeclaration ctor
                        && MemberIdentity.paramKey(ctor.getParameters()).equals(canonicalKey));
                if (canonical && member instanceof NodeWithModifiers<?> ctorNode) {
                    applyAccess(ctorNode, record.getAccessSpecifier());
                }
            }
        } else if (owner instanceof EnumDeclaration enumType) {
            for (BodyDeclaration<?> member : enumType.getMembers()) {
                if (member instanceof ConstructorDeclaration ctor) {
                    ctor.removeModifier(Modifier.Keyword.PUBLIC);
                    ctor.removeModifier(Modifier.Keyword.PROTECTED);
                }
            }
        }
    }

    private static void applyAccess(NodeWithModifiers<?> node, AccessSpecifier access) {
        node.removeModifier(Modifier.Keyword.PUBLIC, Modifier.Keyword.PRIVATE, Modifier.Keyword.PROTECTED);
        switch (access) {
            case PUBLIC -> node.addModifier(Modifier.Keyword.PUBLIC);
            case PRIVATE -> node.addModifier(Modifier.Keyword.PRIVATE);
            case PROTECTED -> node.addModifier(Modifier.Keyword.PROTECTED);
            case NONE -> {
            }
        }
    }
}
