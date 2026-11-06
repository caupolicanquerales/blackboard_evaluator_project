package com.capo.ast_weaver_java.services.weave;

import com.github.javaparser.ast.Modifier;
import com.github.javaparser.ast.body.BodyDeclaration;
import com.github.javaparser.ast.body.EnumConstantDeclaration;
import com.github.javaparser.ast.body.EnumDeclaration;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.Parameter;
import com.github.javaparser.ast.body.RecordDeclaration;
import com.github.javaparser.ast.body.TypeDeclaration;

import java.util.List;
import java.util.Optional;

/**
 * Merges parsed payload members into the owner by AST identity: same key means
 * replace-the-twin (when the text differs) or skip (when it does not); no key means
 * append. Never appends a second member the owner already declares, so re-weaving is
 * idempotent by construction. Record component routing lives here too: on a fresh record
 * shell a `Type name` entry becomes a header component; on an existing record it is
 * never a body member.
 */
public final class MemberWeaver {

    private MemberWeaver() {
    }

    public static boolean merge(TypeDeclaration<?> owner, List<BodyDeclaration<?>> fragments,
            boolean freshRecordShell) {
        boolean changed = false;
        for (BodyDeclaration<?> node : fragments) {
            if (owner instanceof RecordDeclaration record && node instanceof FieldDeclaration field
                    && isComponentShape(field)) {
                if (freshRecordShell && !isStatic(field)) {
                    record.addParameter(componentOf(field));
                    changed = true;
                }
                continue;
            }
            Optional<BodyDeclaration<?>> twin = findTwin(owner, node);
            if (twin.isPresent()) {
                if (!MemberIdentity.normalizeCode(twin.get().toString())
                        .equals(MemberIdentity.normalizeCode(node.toString()))) {
                    twin.get().replace(node);
                    changed = true;
                }
                continue;
            }
            addMember(owner, node);
            changed = true;
        }
        return changed;
    }

    private static void addMember(TypeDeclaration<?> owner, BodyDeclaration<?> node) {
        if (node instanceof EnumConstantDeclaration constant && owner instanceof EnumDeclaration enumType) {
            // Enum constants must precede every other member; the entries list is the
            // only position javac accepts them at.
            enumType.getEntries().add(constant);
            return;
        }
        owner.addMember(node);
    }

    private static Optional<BodyDeclaration<?>> findTwin(TypeDeclaration<?> owner, BodyDeclaration<?> node) {
        String key = MemberIdentity.keyOf(node);
        if (key == null) {
            String text = MemberIdentity.normalizeCode(node.toString());
            return TypeDeclarations.all(owner).stream()
                .filter(existing -> MemberIdentity.normalizeCode(existing.toString()).equals(text))
                .findFirst();
        }
        return TypeDeclarations.all(owner).stream()
            .filter(existing -> key.equals(MemberIdentity.keyOf(existing)))
            .findFirst();
    }

    /** A record component is a single declaration without an initializer. */
    private static boolean isComponentShape(FieldDeclaration field) {
        return field.getVariables().size() == 1
            && field.getVariables().get(0).getInitializer().isEmpty();
    }

    private static boolean isStatic(FieldDeclaration field) {
        return field.hasModifier(Modifier.Keyword.STATIC);
    }

    private static Parameter componentOf(FieldDeclaration field) {
        String prefix = field.getAnnotations().isEmpty() ? ""
            : field.getAnnotations().stream().map(Object::toString)
                .reduce((a, b) -> a + " " + b).orElse("") + " ";
        String declaration = prefix + field.getCommonType().asString() + " "
            + field.getVariables().get(0).getNameAsString();
        return PayloadParser.parameter(declaration);
    }
}
