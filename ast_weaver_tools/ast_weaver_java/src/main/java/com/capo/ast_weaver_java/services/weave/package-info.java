/**
 * Internal pipeline services for {@link com.capo.ast_weaver_java.services.JavaASTWeaver}.
 *
 * <p>The weave is an ordered pipeline; each stage owns exactly one reason to change:
 * <ol>
 *   <li>{@link com.capo.ast_weaver_java.services.weave.PayloadNames} - derives kind, type
 *       name and package from the payload and target path.</li>
 *   <li>{@link com.capo.ast_weaver_java.services.weave.TypeSkeletons} /
 *       {@link com.capo.ast_weaver_java.services.weave.SourceFiles} - creates the AST shell
 *       of a new file, or loads and re-writes an existing one.</li>
 *   <li>{@link com.capo.ast_weaver_java.services.weave.PayloadParser} - the grammar
 *       gateway: the only class that touches JavaParser's static facade, home of the
 *       member-context ladder.</li>
 *   <li>{@link com.capo.ast_weaver_java.services.weave.ImportWeaver},
 *       {@link com.capo.ast_weaver_java.services.weave.MemberWeaver},
 *       {@link com.capo.ast_weaver_java.services.weave.AnnotationWeaver},
 *       {@link com.capo.ast_weaver_java.services.weave.MethodWeaver} - merge each payload
 *       section into the owner AST.</li>
 *   <li>{@link com.capo.ast_weaver_java.services.weave.MemberIdentity} /
 *       {@link com.capo.ast_weaver_java.services.weave.TypeIdentity} /
 *       {@link com.capo.ast_weaver_java.services.weave.TypeDeclarations} - AST-level
 *       identity and structural views used by the merging stages.</li>
 *   <li>{@link com.capo.ast_weaver_java.services.weave.SemanticFixups} - JLS rules the
 *       payloads routinely violate, normalized as AST operations.</li>
 *   <li>{@link com.capo.ast_weaver_java.services.weave.SyntaxGate} - the JDK compiler's
 *       own parser, the last authority before anything is written.</li>
 * </ol>
 *
 * <p>Language knowledge lives in exactly two places: {@code PayloadParser} (contexts in
 * which text may parse) and {@code MemberIdentity}/{@code TypeIdentity} (what makes two
 * members the same member). A future payload incident becomes a regression test against
 * one of these services - not a new patch across the orchestrator.
 */
package com.capo.ast_weaver_java.services.weave;
