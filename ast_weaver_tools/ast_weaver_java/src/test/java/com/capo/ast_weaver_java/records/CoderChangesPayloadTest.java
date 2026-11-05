package com.capo.ast_weaver_java.records;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class CoderChangesPayloadTest {

    @Test
    void constructor_nullImports_becomesEmptyList() {
        CoderChangesPayload payload = payloadWith(null, "return null;");

        assertThat(payload.imports()).isEmpty();
        assertThat(payload.missing()).isEmpty();
    }

    @Test
    void constructor_collectionsAreDefensivelyCopied() {
        List<String> mutableImports = new ArrayList<>(Arrays.asList("java.util.List"));

        CoderChangesPayload payload = payloadWith(mutableImports, "return null;");
        mutableImports.add("java.util.Map");

        assertThat(payload.imports()).containsExactly("java.util.List");
        assertThatThrownBy(() -> payload.imports().add("x"))
            .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void constructor_nullBody_throws() {
        assertThatThrownBy(() -> payloadWith(List.of(), null))
            .isInstanceOf(NullPointerException.class)
            .hasMessageContaining("body");
    }

    private static CoderChangesPayload payloadWith(List<String> imports, String body) {
        return new CoderChangesPayload("T-1", "proj", "src/Main.java", "Main", "run", "java",
            "spring-boot", "run()", "void", "class", null, imports, body, imports, true);
    }
}
