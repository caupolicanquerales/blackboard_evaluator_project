package com.capo.ast_weaver_java.services.weave;

import com.github.javaparser.ast.body.BodyDeclaration;
import com.github.javaparser.ast.body.CompactConstructorDeclaration;
import com.github.javaparser.ast.body.EnumConstantDeclaration;
import com.github.javaparser.ast.body.EnumDeclaration;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.Parameter;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Unit tests per pipeline service: when a future payload incident arrives, the failing
 * component is reproduced against its own class here - not through a full weave - so the
 * fix lands in the one class that owns the behavior.
 */
class WeavePipelineServicesTest {

    // --- PayloadParser: the context ladder ---

    @Test
    void member_parsesFieldWithoutTerminator_throughSecondRung() {
        List<BodyDeclaration<?>> parsed =
            PayloadParser.member("private final String name", "class", "Holder");
        assertThat(parsed).singleElement().isInstanceOf(FieldDeclaration.class);
    }

    @Test
    void member_compactConstructorNeedsRecordContext_ladderFindsIt() {
        List<BodyDeclaration<?>> parsed =
            PayloadParser.member("Sensor { if (value < 0) { throw new IllegalArgumentException(); } }",
                "record", "Sensor");
        assertThat(parsed).singleElement().isInstanceOf(CompactConstructorDeclaration.class);
    }

    @Test
    void member_enumConstantNeedsEnumContext_ladderFindsIt() {
        List<BodyDeclaration<?>> parsed = PayloadParser.member("RED", "enum", "Color");
        assertThat(parsed).singleElement().isInstanceOf(EnumConstantDeclaration.class);
    }

    @Test
    void member_unparseableEverywhere_namesMemberAndEveryRung() {
        assertThatThrownBy(() -> PayloadParser.member("int = = 7", "class", "Broken"))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("does not parse inside Broken")
            .hasMessageContaining("member: int = = 7")
            .hasMessageContaining("member with ';' appended");
    }

    @Test
    void signatureParameters_grammarHandlesGenericsAndVarArgs() {
        Optional<List<Parameter>> params =
            PayloadParser.signatureParameters("counts(Map<String, Integer> ctx, double... rest)");
        assertThat(params).isPresent();
        assertThat(params.get()).hasSize(2);
        assertThat(params.get().get(1).isVarArgs()).isTrue();
    }

    @Test
    void signatureParameters_typeOnlyListFallsBackToLegacySplit() {
        Optional<List<Parameter>> params = PayloadParser.signatureParameters("calculateTax(String)");
        assertThat(params).isPresent();
        assertThat(params.get()).singleElement()
            .extracting(p -> p.getType().asString()).isEqualTo("String");
    }

    // --- MemberIdentity / TypeIdentity: what makes two members one ---

    @Test
    void keyOf_qualifiedAndSimpleSpellingsMatch() {
        MethodDeclaration simple = PayloadParser.methodDeclaration("public String post(String ref) { }");
        MethodDeclaration qualified =
            PayloadParser.methodDeclaration("public java.lang.String post(java.lang.String ref) { }");
        assertThat(MemberIdentity.keyOf(simple)).isEqualTo(MemberIdentity.keyOf(qualified));
    }

    @Test
    void keyOf_overloadsDifferAndCompactIsItsOwnKind() {
        MethodDeclaration one = PayloadParser.methodDeclaration("public void log(String m) { }");
        MethodDeclaration other = PayloadParser.methodDeclaration("public void log(String m, int n) { }");
        assertThat(MemberIdentity.keyOf(one)).isNotEqualTo(MemberIdentity.keyOf(other));
        assertThat(MemberIdentity.keyOf(one)).isEqualTo("log(String)");

        BodyDeclaration<?> compact = PayloadParser.member("Sensor { }", "record", "Sensor").get(0);
        assertThat(MemberIdentity.keyOf(compact)).isEqualTo("compact-ctor()");
    }

    // --- TypeDeclarations / TypeSkeletons: structure and shells ---

    @Test
    void kindOf_reportsWhatTheOwnerReallyIs() {
        var interfaceType = PayloadParser.typeDeclaration("public interface I { }");
        var enumType = PayloadParser.typeDeclaration("public enum E { A }");
        assertThat(TypeDeclarations.kindOf(interfaceType)).isEqualTo("interface");
        assertThat(TypeDeclarations.kindOf(enumType)).isEqualTo("enum");
    }

    @Test
    void all_seesEnumConstantsThatGetMembersOmits() {
        var enumType = (EnumDeclaration) PayloadParser.typeDeclaration(
            "public enum E { A, B; public int x() { return 1; } }");
        assertThat(enumType.getMembers()).hasSize(1);
        assertThat(TypeDeclarations.all(enumType)).hasSize(3);
    }

    @Test
    void shell_exceptionExtendsRuntimeExceptionAtTheAstLevel() {
        assertThat(TypeSkeletons.create("exception", "FlowFailed", "com.x").toString())
            .contains("public class FlowFailed extends RuntimeException");
    }

    // --- SyntaxGate: the compiler's own verdict ---

    @Test
    void gate_flagsSyntaxWithLinesAndIgnoresUnresolvedTypes() {
        assertThat(SyntaxGate.problems("package p; public class A { void x( { }"))
            .anyMatch(problem -> problem.startsWith("line "));
        assertThat(SyntaxGate.problems("package p; public interface I { void save(Account a); }"))
            .isEmpty();
    }

    // --- PayloadNames: payload hygiene ---

    @Test
    void normalizeKind_rejectsUnknownKindsAndDefaultsToClass() {
        assertThat(PayloadNames.normalizeKind(null)).isEqualTo("class");
        assertThat(PayloadNames.normalizeKind(" Record ")).isEqualTo("record");
        assertThatThrownBy(() -> PayloadNames.normalizeKind("annotation"))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("Unsupported payload kind");
    }
}
