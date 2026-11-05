package com.capo.ast_weaver_java.services;

import com.capo.ast_weaver_java.records.CoderChangesPayload;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class JavaASTWeaverTest {

    private static final String TAX_CALCULATOR = """
        public class TaxCalculator {
            public double calculateTax(double rate) {
                return 0.0;
            }

            public double calculateTax(double rate, double net) {
                throw new UnsupportedOperationException();
            }
        }
        """;

    @TempDir
    Path tempDir;

    @Test
    void weave_singleMethod_replacesBody() throws IOException {
        Path file = givenSource("class Greeter { public String greet() { return \"TODO\"; } }");

        JavaASTWeaver.weave(file, payload("Greeter", "greet", "greet()", "String", null, List.of(),
            "return \"hello\";"));

        assertThat(Files.readString(file)).contains("return \"hello\";").doesNotContain("TODO");
    }

    @Test
    void weave_overloads_selectsMethodMatchingSignature() throws IOException {
        Path file = givenSource(TAX_CALCULATOR);

        JavaASTWeaver.weave(file, payload("TaxCalculator", "calculateTax", "calculateTax(double rate, double net)",
            "double", null, List.of(), "return rate * net;"));

        String result = Files.readString(file);
        assertThat(result).contains("return rate * net;").contains("return 0.0;");
    }

    @Test
    void weave_noOverloadMatchesSignature_createsThatOverload() throws IOException {
        Path file = givenSource(TAX_CALCULATOR);

        JavaASTWeaver.weave(file, payload("TaxCalculator", "calculateTax", "calculateTax(String code)",
            "double", null, List.of(), "return code.length();"));

        String result = Files.readString(file);
        assertThat(result).contains("calculateTax(String code)").contains("return code.length();")
            .contains("return 0.0;").contains("UnsupportedOperationException");
    }

    @Test
    void weave_missingFile_createsClassWithPackageAndMembers() throws IOException {
        Path file = tempDir.resolve("src/main/java/com/example/OpenAccountCommand.java");

        JavaASTWeaver.weave(file, payload("com.example.OpenAccountCommand", "customerId",
            "customerId()", "String",
            List.of("private final String customerId;",
                    "public OpenAccountCommand(String customerId) { this.customerId = customerId; }"),
            "return customerId;"));

        String result = Files.readString(file);
        assertThat(result).contains("package com.example;").contains("public class OpenAccountCommand")
            .contains("this.customerId = customerId")
            .contains("public String customerId()").contains("return customerId;")
            .doesNotContain("public class OpenAccountCommandpublic");
    }

    @Test
    void weave_interfaceKind_createsAbstractSignaturesOnly() throws IOException {
        Path file = tempDir.resolve("src/main/java/com/example/AccountRepository.java");

        JavaASTWeaver.weave(file, payload("com.example.AccountRepository", "findById",
            "findById(String id)", "Account", "interface",
            List.of("Account findById(String id);", "void save(Account account);"), ""));

        String result = Files.readString(file);
        assertThat(result).contains("public interface AccountRepository")
            .contains("Account findById(String id);").contains("void save(Account account);")
            .doesNotContain("throw");
    }

    @Test
    void weave_recordKind_createsComponents() throws IOException {
        Path file = tempDir.resolve("src/main/java/com/example/AccountCreatedEvent.java");

        JavaASTWeaver.weave(file, payload("com.example.AccountCreatedEvent", "accountId",
            "accountId()", "String", "record",
            List.of("String accountId", "String customerId"), ""));

        assertThat(Files.readString(file))
            .contains("public record AccountCreatedEvent(String accountId, String customerId)");
    }

    @Test
    void weave_exceptionKind_extendsRuntimeException() throws IOException {
        Path file = tempDir.resolve("src/main/java/com/example/InvalidTransitionException.java");

        JavaASTWeaver.weave(file, payload("com.example.InvalidTransitionException", "ctor",
            "ctor(String m)", "void", "exception",
            List.of("public InvalidTransitionException(String m) { super(m); }"), ""));

        assertThat(Files.readString(file)).contains("extends RuntimeException")
            .contains("super(m);");
    }

    @Test
    void weave_samePayloadTwice_isIdempotent() throws IOException {
        Path file = tempDir.resolve("src/main/java/com/example/Holder.java");
        CoderChangesPayload command = payload("com.example.Holder", "hold", "hold(String x)", "String",
            List.of("private final String value;"), "return value;");

        JavaASTWeaver.weave(file, command);
        String first = Files.readString(file);
        JavaASTWeaver.weave(file, command);
        String second = Files.readString(file);

        assertThat(countOf(second, "private final String value")).isEqualTo(1);
        assertThat(second).contains("return value;");
        assertThat(first).isNotNull();
    }

    @Test
    void weave_blankSignatureWithOverloads_throwsAmbiguous() throws IOException {
        Path file = givenSource(TAX_CALCULATOR);

        assertThatThrownBy(() -> JavaASTWeaver.weave(file,
            payload("TaxCalculator", "calculateTax", "", "double", null, List.of(), "return 1.0;")))
            .isInstanceOf(IllegalStateException.class)
            .hasMessageContaining("Ambiguous overload");
    }

    @Test
    void weave_invalidBody_throwsAndLeavesFileUnchanged() throws IOException {
        Path file = givenSource(TAX_CALCULATOR);

        assertThatThrownBy(() -> JavaASTWeaver.weave(file,
            payload("TaxCalculator", "calculateTax", "calculateTax(double rate, double net)", "double",
                null, List.of(), "return ??? ;")))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("does not parse");
        assertThat(Files.readString(file)).isEqualTo(TAX_CALCULATOR);
    }

    @Test
    void weave_addsImports_skipsJavaLangAndDuplicates() throws IOException {
        Path file = givenSource("import java.util.List;\npublic class Importer {\n"
            + " public void target() { return; }\n}\n");

        JavaASTWeaver.weave(file, payload("Importer", "target", "target()", "void", null, List.of(),
            "System.gc();", "java.util.List", "java.lang.String", "java.util.Map"));

        String result = Files.readString(file);
        assertThat(countOf(result, "import java.util.List;")).isEqualTo(1);
        assertThat(result).contains("import java.util.Map;").doesNotContain("import java.lang.String;");
    }

    @Test
    void weave_existingFile_preservesSurroundingFormatting() throws IOException {
        String source = """
            public class Formatter {
                // keep-me comment
                public int untouched() {
                    return    42;
                }

                public int target() {
                    return 0;
                }
            }
            """;
        Path file = givenSource(source);

        JavaASTWeaver.weave(file, payload("Formatter", "target", "target()", "int", null, List.of(), "return 7;"));

        String result = Files.readString(file);
        assertThat(result).contains("// keep-me comment").contains("return    42;").contains("return 7;");
    }

    private Path givenSource(String source) throws IOException {
        Path file = tempDir.resolve("Source.java");
        Files.writeString(file, source);
        return file;
    }

    private static CoderChangesPayload payload(String export, String method, String signature, String returns,
            List<String> members, String body) {
        return payload(export, method, signature, returns, null, members, body);
    }

    private static CoderChangesPayload payload(String export, String method, String signature, String returns,
            String kind, List<String> members, String body, String... imports) {
        return new CoderChangesPayload("T-1", "proj", "ignored.java", export, method, "java",
            "spring-boot", signature, returns, kind, members, List.of(imports), body, List.of(), true);
    }

    private static long countOf(String text, String token) {
        return text.split(Pattern.quote(token), -1).length - 1L;
    }
}
