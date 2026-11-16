package com.capo.ast_weaver_java.services;

import com.capo.ast_weaver_java.records.CoderChangesPayload;
import com.capo.ast_weaver_java.services.weave.AnnotationWeaver;
import com.capo.ast_weaver_java.services.weave.ImportWeaver;
import com.capo.ast_weaver_java.services.weave.MemberWeaver;
import com.capo.ast_weaver_java.services.weave.MethodWeaver;
import com.capo.ast_weaver_java.services.weave.PayloadNames;
import com.capo.ast_weaver_java.services.weave.PayloadParser;
import com.capo.ast_weaver_java.services.weave.SemanticFixups;
import com.capo.ast_weaver_java.services.weave.SourceFiles;
import com.capo.ast_weaver_java.services.weave.SuperTypeWeaver;
import com.capo.ast_weaver_java.services.weave.TypeDeclarations;
import com.capo.ast_weaver_java.services.weave.TypeSkeletons;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.RecordDeclaration;
import com.github.javaparser.ast.body.TypeDeclaration;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Objects;

/**
 * Weaves a {@link CoderChangesPayload} into a Java source file: a thin orchestration of
 * the single-responsibility services in {@code services.weave}. No language knowledge and
 * no file mechanics live here - the pipeline only decides the ORDER of the stages:
 *
 * <pre>
 * PayloadNames      -> kind, type, package            (where and as what)
 * TypeSkeletons /   -> AST shell or load + preserve   (the canvas)
 * SourceFiles
 * ImportWeaver      -> payload.imports()
 * TypeDeclarations  -> the owner type inside the file
 * SuperTypeWeaver   -> payload extends/implements clauses (adapters IS-A their port)
 * PayloadParser     -> every member text via the context ladder
 * MemberWeaver      -> merge by AST identity (replace twins, never duplicate)
 * AnnotationWeaver  -> type annotations
 * MethodWeaver      -> target method + body, or interface signature
 * SemanticFixups    -> JLS access rules the payloads violate
 * SourceFiles       -> render, SyntaxGate, write-if-changed
 * </pre>
 *
 * <h2>Managing a future failure</h2>
 * A failing payload names its member and the grammar rung that rejected it. The recovery
 * protocol: add it as a regression test against {@link com.capo.ast_weaver_java.services.weave.PayloadParser}
 * or {@code JavaASTWeaverGenericShapesTest}; in almost every case the ladder already
 * handles the shape and no code changes at all. Only a genuinely new JLS member context
 * adds a rung to {@code PayloadParser}, an identity rule to {@code MemberIdentity}, or a
 * violation rule to {@code SemanticFixups} - those are the only classes that hold
 * language knowledge, and they are independently testable.
 */
public final class JavaASTWeaver {

    private JavaASTWeaver() {
    }

    public static void weave(Path targetPath, CoderChangesPayload payload) throws IOException {
        Objects.requireNonNull(targetPath, "targetPath is required");
        Objects.requireNonNull(payload, "payload is required");

        String kind = PayloadNames.normalizeKind(payload.kind());
        String simpleTypeName = PayloadNames.simpleTypeName(payload.export());
        List<String> typeParameters = PayloadNames.typeParameters(payload.export());
        boolean newFile = !Files.isRegularFile(targetPath);

        CompilationUnit cu = newFile
            ? TypeSkeletons.create(kind, simpleTypeName, typeParameters,
                PayloadNames.packageOf(payload.export(), targetPath))
            : SourceFiles.loadExisting(targetPath);

        ImportWeaver.apply(cu, payload.imports());
        TypeDeclaration<?> owner = newFile
            ? cu.getTypes().get(0)
            : TypeDeclarations.findOrCreate(cu, simpleTypeName, kind, typeParameters);

        if (owner != null) {
            SuperTypeWeaver.apply(owner, payload.extendsType(), payload.implementsTypes());
            MemberWeaver.merge(owner,
                PayloadParser.members(payload.members(), TypeDeclarations.kindOf(owner), simpleTypeName),
                newFile && owner instanceof RecordDeclaration);
            AnnotationWeaver.applyAll(owner, payload.annotations());

            if (!"interface".equals(kind) && !payload.body().isBlank()) {
                // A payload whose method name IS the class name declares a constructor:
                // it must splice into a ConstructorDeclaration - a MethodDeclaration
                // named like the class can never assign final fields (T2-017 storm).
                com.github.javaparser.ast.body.BodyDeclaration<?> target;
                if (MethodWeaver.declaresConstructor(payload.method(), owner)) {
                    target = MethodWeaver.selectOrCreateConstructor(owner, payload);
                } else {
                    // Full-declaration signatures replace the method wholesale; the bare
                    // contract spelling keeps the create/select + reconcile path.
                    target = MethodWeaver.fullDeclaration(payload)
                        .map(declaration -> MethodWeaver.replaceInPlace(owner, declaration))
                        .orElseGet(() -> {
                            MethodDeclaration selected = MethodWeaver.selectOrCreate(owner, payload);
                            MethodWeaver.reconcileFromSignature(selected, payload);
                            return selected;
                        });
                }
                AnnotationWeaver.applyAll(target, payload.methodAnnotations());
                if (target instanceof MethodDeclaration asMethod) {
                    asMethod.setBody(PayloadParser.body(payload.body()));
                } else if (target instanceof ConstructorDeclaration asCtor) {
                    asCtor.setBody(PayloadParser.body(payload.body()));
                }
            } else if ("interface".equals(kind)) {
                MethodWeaver.addAbstractIfAbsent(owner, payload)
                    .ifPresent(method -> AnnotationWeaver.applyAll(method, payload.methodAnnotations()));
            }

            SemanticFixups.enforceConstructorAccess(owner);
        }

        SourceFiles.writeValidated(targetPath, cu, newFile);
    }
}
