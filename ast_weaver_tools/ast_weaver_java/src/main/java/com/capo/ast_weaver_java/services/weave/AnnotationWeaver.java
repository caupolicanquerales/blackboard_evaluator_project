package com.capo.ast_weaver_java.services.weave;

import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.expr.AnnotationExpr;
import com.github.javaparser.ast.nodeTypes.NodeWithAnnotations;

import java.util.List;

/**
 * Applies the payload's framework annotations ({@code @RestController},
 * {@code @PostMapping("/ingress")}) to a node. Identity is the annotation's simple AST
 * name, so the same annotation written qualified or simple never duplicates and
 * re-weaving stays idempotent.
 */
public final class AnnotationWeaver {

    private AnnotationWeaver() {
    }

    public static void applyAll(Node target, List<String> annotations) {
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
            AnnotationExpr parsed;
            try {
                parsed = PayloadParser.annotation(text);
            } catch (RuntimeException ex) {
                throw new IllegalArgumentException("Payload annotation does not parse: " + raw
                    + " (" + ParseErrors.firstLineOf(ex.getMessage()) + ")", ex);
            }
            String name = parsed.getName().getIdentifier();
            boolean present = holder.getAnnotations().stream()
                .anyMatch(annotation -> annotation.getName().getIdentifier().equals(name));
            if (!present) {
                holder.addAnnotation(parsed);
            }
        }
    }
}
