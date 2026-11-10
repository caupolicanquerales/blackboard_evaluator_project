package com.capo.ast_weaver_java.services;

import com.capo.ast_weaver_java.records.CoderChangesPayload;
import java.io.StringWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.regex.Pattern;
import javax.tools.JavaCompiler;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Regression suite for the grammar-ladder rewrite. Every payload shape here was NEVER handled
 * by the retired regex/surgery mechanisms; each test asks the question the old service could
 * only answer after an incident: does a shape we have not seen before still weave, stay
 * idempotent under re-weave, and compile with the real javac?
 */
class JavaASTWeaverGenericShapesTest {

    @TempDir
    Path tempDir;

    @Test
    void weave_newEnumWithConstantsAndMethod_compilesAndSurvivesRewrite() throws IOException {
        Path file = typedTarget("com.x.Status");

        JavaASTWeaver.weave(file, payload("com.x.Status", "pretty", "pretty()", "String", "enum",
            List.of("NEW", "public String pretty() { return name().toLowerCase(); }"), ""));
        assertCompiles(file);

        JavaASTWeaver.weave(file, payload("com.x.Status", "pretty", "pretty()", "String", "enum",
            List.of("NEW", "OLD", "public String pretty() { return name().toLowerCase(); }"), ""));

        String result = Files.readString(file);
        assertThat(countOf(result, "NEW")).isEqualTo(1L);
        assertThat(countOf(result, "String pretty(")).isEqualTo(1L);
        assertCompiles(file);
    }

    @Test
    void weave_enumConstantWithArgumentsAndCtor_keepsLegalMemberOrderAndCompiles() throws IOException {
        Path file = typedTarget("com.x.Rank");

        JavaASTWeaver.weave(file, payload("com.x.Rank", "code", "code()", "int", "enum",
            List.of("ACTIVE(1)", "INACTIVE(0)", "private final int code;",
                    "public Rank(int code) { this.code = code; }"), ""));

        assertCompiles(file);
    }

    @Test
    void weave_recordProcessSequence_survivesThreeRealisticRewrites() throws IOException {
        Path file = typedTarget("com.x.Money");

        JavaASTWeaver.weave(file, payload("com.x.Money", "cents", "cents()", "int", "record",
            List.of("int cents"), "return cents;"));
        assertCompiles(file);

        JavaASTWeaver.weave(file, payload("com.x.Money", "cents", "cents()", "int", "record",
            List.of("int cents", "public Money plus(Money other) { return new Money(cents + other.cents); }"),
            ""));
        assertThat(countOf(Files.readString(file), "Money plus(")).isEqualTo(1L);
        assertCompiles(file);

        JavaASTWeaver.weave(file, payload("com.x.Money", "cents", "cents()", "int", "record",
            List.of("int cents",
                    "public Money plus(Money other) { return new Money(cents + other.cents + 1); }"), ""));

        String result = Files.readString(file);
        assertThat(result).contains("+ 1");
        assertThat(countOf(result, "Money plus(")).isEqualTo(1L);
        assertThat(countOf(result, "record Money(int cents)")).isEqualTo(1L);
        assertCompiles(file);
    }

    @Test
    void weave_multiDeclaratorField_compilesAndStaysIdempotent() throws IOException {
        Path file = typedTarget("com.x.Box");

        CoderChangesPayload command = payload("com.x.Box", "area", "area()", "int", "class",
            List.of("private final int width, height;",
                    "public Box(int width, int height) { this.width = width; this.height = height; }"),
            "return width * height;");
        JavaASTWeaver.weave(file, command);
        assertCompiles(file);

        JavaASTWeaver.weave(file, command);
        assertThat(countOf(Files.readString(file), "private final int width, height")).isEqualTo(1L);
        assertCompiles(file);
    }

    @Test
    void weave_genericMethodMember_isIdempotentAndCompiles() throws IOException {
        Path file = typedTarget("com.x.Wrap");

        JavaASTWeaver.weave(file, payload("com.x.Wrap", "run", "run()", "void", "class",
            List.of("public <T> java.util.List<T> wrap(T value) { return java.util.List.of(value); }"),
            "// wired"));

        assertCompiles(file);
        String once = Files.readString(file);
        assertThat(once).contains("<T> java.util.List<T> wrap(T value)");

        JavaASTWeaver.weave(file, payload("com.x.Wrap", "run", "run()", "void", "class",
            List.of("public <T> java.util.List<T> wrap(T value) { return java.util.List.of(value); }"),
            "// wired"));
        assertThat(countOf(Files.readString(file), "wrap(T value)")).isEqualTo(1L);
    }

    @Test
    void weave_varArgsSignature_replacesExistingMethodWithoutDuplicate() throws IOException {
        Path file = givenSource("com.x.LogSink", """
            package com.x;

            public class LogSink {
                public void log(String... msgs) {
                    System.out.println(msgs.length);
                }
            }
            """);

        JavaASTWeaver.weave(file, payload("com.x.LogSink", "log", "log(String... messages)", "void",
            "class", List.of(), "System.out.println(\"v2\");"));

        String result = Files.readString(file);
        assertThat(result).contains("v2").doesNotContain("msgs.length");
        assertThat(countOf(result, "void log(")).isEqualTo(1L);
        assertCompiles(file);
    }

    @Test
    void weave_wildcardGenericsInSignature_createAndMatch() throws IOException {
        Path file = typedTarget("com.x.Counts");

        JavaASTWeaver.weave(file, payload("com.x.Counts", "counts", "counts(List<? extends Number> source)",
            "List<? extends Number>", "class", List.of(), "return source;", "java.util.List"));

        String result = Files.readString(file);
        assertThat(result).contains("List<? extends Number> counts(List<? extends Number> source)");
        assertCompiles(file);
    }

    @Test
    void weave_textBlockBody_weavesAndCompiles() throws IOException {
        Path file = typedTarget("com.x.Greeter");

        JavaASTWeaver.weave(file, payload("com.x.Greeter", "hello", "hello()", "String", "class",
            List.of(), "return \"\"\"\n            hi\n            \"\"\";"));

        assertCompiles(file);
    }

    @Test
    void weave_interfaceDefaultMethod_compiles() throws IOException {
        Path file = typedTarget("com.x.Payments");

        JavaASTWeaver.weave(file, payload("com.x.Payments", "isFree", "isFree()", "boolean", "interface",
            List.of("default boolean isFree() { return false; }", "boolean charge();"), ""));

        String result = Files.readString(file);
        assertThat(result).contains("default boolean isFree()").contains("boolean charge();");
        assertCompiles(file);
    }

    @Test
    void weave_staticInitializerMember_addedOnceAcrossRewrites() throws IOException {
        Path file = typedTarget("com.x.Holder2");

        CoderChangesPayload command = payload("com.x.Holder2", "run", "run()", "void", "class",
            List.of("private static int counter;", "static { counter++; }"), "// ok");
        JavaASTWeaver.weave(file, command);
        JavaASTWeaver.weave(file, command);

        String result = Files.readString(file);
        assertThat(countOf(result, "static {")).isEqualTo(1L);
        assertThat(countOf(result, "private static int counter")).isEqualTo(1L);
        assertCompiles(file);
    }

    @Test
    void weave_annotationTypeMember_simpleAndQualifiedNamesCountOnce() throws IOException {
        Path file = typedTarget("com.x.Marked");

        // A nested annotation type CAN annotate its own enclosing class's members, but not
        // the class that contains it (javac cannot resolve that scope) - so the marker
        // lands on the method, and the two spellings are tested for one identity.
        JavaASTWeaver.weave(file, annotatedPayload("com.x.Marked", "run", "run()", "void", "class",
            List.of("@interface Marker { }"), "// ok", List.of(), List.of("Marker")));
        JavaASTWeaver.weave(file, annotatedPayload("com.x.Marked", "run", "run()", "void", "class",
            List.of("@interface Marker { }"), "// ok", List.of(), List.of("@com.x.Marked.Marker")));

        String result = Files.readString(file);
        assertThat(countOf(result, "@interface Marker")).isEqualTo(1L);
        assertThat(countOf(result, "@Marker")).isEqualTo(1L);
        assertCompiles(file);
    }

    @Test
    void weave_canonicalConstructorMember_replacesExistingBodyOnce() throws IOException {
        Path file = givenSource("com.x.Conf", """
            package com.x;

            public class Conf {
                private final String path;

                public Conf(String path) {
                    this.path = path;
                }
            }
            """);

        JavaASTWeaver.weave(file, payload("com.x.Conf", "path", "path()", "String", "class",
            List.of("public Conf(String path) { this.path = path.intern(); }"), "return path;"));

        String result = Files.readString(file);
        assertThat(result).contains("path.intern()").doesNotContain("this.path = path;");
        assertThat(countOf(result, "Conf(String path)")).isEqualTo(1L);
        assertCompiles(file);
    }

    @Test
    void weave_nestedClassMemberTwice_replacesTwinAndCompiles() throws IOException {
        Path file = givenSource("com.x.Outer", """
            package com.x;

            public class Outer {
                public static class Inner {
                    private int stale;
                }
            }
            """);

        JavaASTWeaver.weave(file, payload("com.x.Outer", "run", "run()", "void", "class",
            List.of("public static class Inner { private int fresh; }"), "// ok"));

        String result = Files.readString(file);
        assertThat(countOf(result, "class Inner")).isEqualTo(1L);
        assertThat(result).contains("fresh").doesNotContain("stale");
        assertCompiles(file);
    }

    @Test
    void weave_exceptionKindIntoUnrelatedExistingFile_createsExtendingSubclass() throws IOException {
        Path file = givenSource("com.x.Other", "package com.x;\n\npublic class Other {\n    public void keep() { }\n}\n");

        JavaASTWeaver.weave(file, payload("com.x.FlowFailedException", "ctor", "ctor(String m)", "void",
            "exception", List.of("public FlowFailedException(String m) { super(m); }"), ""));

        String result = Files.readString(file);
        assertThat(result).contains("class FlowFailedException extends RuntimeException")
            .contains("keep()");
        // the file now holds two top-level types; javac checks the public-name/file-name rule,
        // so compile the pair the way a build would: extract the new type into its own file
        Path extra = typedTarget("com.x.FlowFailedException");
        Files.writeString(extra, result.replace("public class Other {", "class Other {"));
        assertCompiles(extra);
    }

    @Test
    void weave_enumKindIntoUnrelatedExistingFile_createsEnumShell() throws IOException {
        Path file = givenSource("com.x.Wrapper", "package com.x;\n\npublic class Wrapper {\n    public void keep() { }\n}\n");

        JavaASTWeaver.weave(file, payload("com.x.Direction", "name", "name()", "String", "enum",
            List.of("NORTH", "SOUTH"), ""));

        String result = Files.readString(file);
        assertThat(result).contains("public enum Direction").contains("NORTH").contains("SOUTH");

        Path extra = typedTarget("com.x.Direction");
        Files.writeString(extra, result.replace("public class Wrapper {", "class Wrapper {"));
        assertCompiles(extra);
    }

    @Test
    void weave_garbageMember_reportsTheMemberAndTheGrammarRungs() throws IOException {        Path file = typedTarget("com.x.Broken2");

        assertThatThrownBy(() -> JavaASTWeaver.weave(file, payload("com.x.Broken2", "run", "run()",
            "void", "class", List.of("int = = 7"), "// ok")))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("does not parse inside Broken2")
            .hasMessageContaining("member: int = = 7");
    }

    @Test
    void weave_genericClassExport_newFileKeepsTypeParameterAndCompiles() throws IOException {
        // The T2-006 incident: export declared BoundedEventChannel<T> but the created shell
        // was plain `class BoundedEventChannel`, so every member mentioning T died in javac
        // and no coder retry could escape the identical failure.
        Path file = typedTarget("com.x.Channel");
        CoderChangesPayload command = payload("com.x.Channel<T>", "publish", "publish(T event)", "void", "class",
            List.of("private final T seed;", "public Channel(T seed) { this.seed = seed; }",
                    "public T seed() { return seed; }"), "");

        JavaASTWeaver.weave(file, command);
        String result = Files.readString(file);
        assertThat(result).contains("class Channel<T>");
        assertCompiles(file);

        JavaASTWeaver.weave(file, command);
        String rewoven = Files.readString(file);
        assertThat(countOf(rewoven, "class Channel")).isEqualTo(1L);
        assertThat(countOf(rewoven, "<T>")).isEqualTo(1L);
        assertCompiles(file);
    }

    @Test
    void weave_genericClassExportOntoExistingPlainShell_addsParameterOnce() throws IOException {
        Path file = givenSource("com.x.Box", """
            package com.x;

            public class Box {
                public void keep() { }
            }
            """);

        JavaASTWeaver.weave(file, payload("com.x.Box<T>", "value", "value()", "T", "class",
            List.of("private final T value;", "public Box(T value) { this.value = value; }"), "return value;"));
        String result = Files.readString(file);
        assertThat(result).contains("class Box<T>").contains("keep()");
        assertCompiles(file);

        JavaASTWeaver.weave(file, payload("com.x.Box<T>", "value", "value()", "T", "class",
            List.of("private final T value;", "public Box(T value) { this.value = value; }"), "return value;"));
        String rewoven = Files.readString(file);
        assertThat(countOf(rewoven, "<T>")).isEqualTo(1L);
        assertCompiles(file);
    }

    @Test
    void weave_multiParameterBoundedExport_splitsParametersNotWords() throws IOException {
        Path file = typedTarget("com.x.Table");

        JavaASTWeaver.weave(file, payload("com.x.Table<K, V extends Comparable<V>>", "lookup", "lookup(K key)", "V",
            "class", List.of(), "return null;"));

        String result = Files.readString(file);
        assertThat(result).contains("class Table<K, V extends Comparable<V>>");
        assertCompiles(file);
    }

    @Test
    void weave_adapterPayloadWithImplements_landsOnPortAndCompiles() throws IOException {
        // The T2-037 incident: the frozen test demanded `isInstanceOf(TelemetryStreamGateway.class)`
        // and the payload had no field to say it, so no coder retry could ever converge.
        Path port = givenSource("com.x.StreamPort", """
            package com.x;

            public interface StreamPort {
                void publish(String item);
            }
            """);
        Path file = typedTarget("com.x.Reactor");
        CoderChangesPayload command = superPayload("com.x.Reactor", "publish", "publish(String item)", "void",
            "class", List.of("public void publish(String item) { }"), "// no-op", "", List.of("StreamPort"));

        JavaASTWeaver.weave(file, command);
        String result = Files.readString(file);
        assertThat(result).contains("class Reactor implements StreamPort");
        assertCompiles(port, file);

        JavaASTWeaver.weave(file, command);
        String rewoven = Files.readString(file);
        assertThat(countOf(rewoven, "implements StreamPort")).isEqualTo(1L);
        assertCompiles(port, file);
    }

    @Test
    void weave_extendsClause_replacesOnlyTheExceptionPlaceholderAndKeepsRealParents() throws IOException {
        Path base = givenSource("com.x.BaseChannel", """
            package com.x;

            public abstract class BaseChannel {
                public abstract String name();
            }
            """);
        Path file = typedTarget("com.x.Failure");

        JavaASTWeaver.weave(file, superPayload("com.x.Failure", "name", "name()", "String", "exception",
            List.of(), "return \"failure\";", "BaseChannel", List.of()));
        String result = Files.readString(file);
        assertThat(result).contains("extends BaseChannel").doesNotContain("extends RuntimeException");
        assertCompiles(base, file);
    }

    @Test
    void weave_staticFactorySignature_reconcilesExistingInstanceMethod() throws IOException {
        // The T2-031 trap: the frozen test calls Resp.from(record) from a static context
        // while the landed method is an instance one. Signature tokens used to be dropped
        // for existing methods, so no re-emit could ever converge.
        Path file = givenSource("com.x.Resp", """
            package com.x;

            public class Resp {
                private final String value;

                public Resp(String value) {
                    this.value = value;
                }

                public Resp from(String raw) {
                    return new Resp(raw);
                }
            }
            """);

        JavaASTWeaver.weave(file, payload("com.x.Resp", "from", "public static Resp from(String raw)", "Resp",
            "class", List.of(), "return new Resp(raw.intern());"));
        String result = Files.readString(file);
        assertThat(result).contains("public static Resp from(String raw)");
        assertCompiles(file);

        JavaASTWeaver.weave(file, payload("com.x.Resp", "from", "public static Resp from(String raw)", "Resp",
            "class", List.of(), "return new Resp(raw.intern());"));
        assertThat(countOf(Files.readString(file), "Resp from(String")).isEqualTo(1L);
        assertCompiles(file);
    }

    @Test
    void weave_fullDeclarationSignature_replacesMethodWholesaleKeepsAnnotations() throws IOException {
        // Day-2 surgery: the signature may be a COMPLETE declaration; then the method is
        // swapped in full text - modifiers, method-level generics, everything rides the
        // text. No schema field is needed for a language shape the tool has not seen.
        Path file = givenSource("com.x.Maper", """
            package com.x;

            public class Maper {
                @Deprecated
                public Object map(Object in) {
                    return in.toString();
                }
            }
            """);

        CoderChangesPayload command = payload("com.x.Maper", "map", "public static <T> T map(T in)", "T",
            "class", List.of(), "return in;");
        JavaASTWeaver.weave(file, command);
        String result = Files.readString(file);
        assertThat(result).contains("public static <T> T map(T in)").contains("@Deprecated");
        assertCompiles(file);

        JavaASTWeaver.weave(file, command);
        String rewoven = Files.readString(file);
        assertThat(countOf(rewoven, "T map(T in)")).isEqualTo(1L);
        assertThat(countOf(rewoven, "@Deprecated")).isEqualTo(1L);
        assertCompiles(file);
    }

    private static CoderChangesPayload superPayload(String export, String method, String signature,
            String returns, String kind, List<String> members, String body,
            String extendsType, List<String> implementsTypes) {
        return new CoderChangesPayload("T-1", "proj", "ignored.java", export, method, "java",
            "spring-boot", signature, returns, kind, members, List.of(), body, List.of(),
            List.of(), List.of(), true, extendsType, implementsTypes);
    }

    private Path typedTarget(String export) throws IOException {
        Path file = tempDir.resolve(export.substring(export.lastIndexOf('.') + 1) + ".java");
        return file;
    }

    private Path givenSource(String export, String source) throws IOException {
        Path file = typedTarget(export);
        Files.writeString(file, source);
        return file;
    }

    private static CoderChangesPayload payload(String export, String method, String signature, String returns,
            String kind, List<String> members, String body, String... imports) {
        return new CoderChangesPayload("T-1", "proj", "ignored.java", export, method, "java",
            "spring-boot", signature, returns, kind, members, List.of(imports), body, List.of(), true);
    }

    private static CoderChangesPayload annotatedPayload(String export, String method, String signature,
            String returns, String kind, List<String> members, String body,
            List<String> annotations, List<String> methodAnnotations) {
        return new CoderChangesPayload("T-1", "proj", "ignored.java", export, method, "java",
            "spring-boot", signature, returns, kind, members, List.of(), body, List.of(),
            annotations, methodAnnotations, true);
    }

    /** The real compiler, not the parse-only gate: full javac run so semantics are proven too. */
    private static void assertCompiles(Path... files) throws IOException {
        JavaCompiler javac = ToolProvider.getSystemJavaCompiler();
        assertThat(javac).as("tests require a JDK (javac), not a JRE").isNotNull();
        StringWriter log = new StringWriter();
        List<String> diagnostics = new java.util.ArrayList<>();
        Path out = files[0].resolveSibling("classes");
        Files.createDirectories(out);
        try (StandardJavaFileManager fm = javac.getStandardFileManager(
                d -> diagnostics.add("line " + d.getLineNumber() + ": " + d.getMessage(null)), null, null)) {
            Iterable<? extends javax.tools.JavaFileObject> units = fm.getJavaFileObjects(
                java.util.Arrays.stream(files).map(Path::toFile).toArray(java.io.File[]::new));
            List<String> options = List.of("-proc:none", "-d", out.toString());
            boolean ok = javac.getTask(log, fm, null, options, List.of(), units).call();
            assertThat(ok).as("woven source must compile:%n%s%n%s %s", files[0], log, diagnostics).isTrue();
        }
    }

    private static long countOf(String text, String token) {
        return text.split(Pattern.quote(token), -1).length - 1L;
    }
}
