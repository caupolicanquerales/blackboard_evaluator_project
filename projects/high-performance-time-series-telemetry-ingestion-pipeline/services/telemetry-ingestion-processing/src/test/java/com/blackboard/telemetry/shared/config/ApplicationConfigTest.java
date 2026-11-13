package com.blackboard.telemetry;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.yaml.snakeyaml.Yaml;

class ApplicationConfigTest {

    private static List<Map<String, Object>> documents;

    @BeforeAll
    static void loadYaml() throws Exception {
        documents = new ArrayList<>();
        try (InputStream in = ApplicationConfigTest.class.getResourceAsStream("/application.yml")) {
            assertThat(in).as("application.yml on classpath").isNotNull();
            for (Object doc : new Yaml().loadAll(in)) {
                Map<String, Object> flat = new LinkedHashMap<>();
                if (doc instanceof Map<?, ?> map) {
                    flatten("", map, flat);
                }
                documents.add(flat);
            }
        }
    }

    private static void flatten(String prefix, Map<?, ?> map, Map<String, Object> out) {
        map.forEach((k, v) -> {
            String key = prefix.isEmpty() ? String.valueOf(k) : prefix + "." + k;
            if (v instanceof Map<?, ?> nested) {
                flatten(key, nested, out);
            } else {
                out.put(key, v);
            }
        });
    }

    private static Map<String, Object> mainDocument() {
        return documents.stream()
                .filter(d -> !d.containsKey("spring.config.activate.on-profile"))
                .findFirst().orElseThrow();
    }

    private static Map<String, Object> testDocument() {
        return documents.stream()
                .filter(d -> "test".equals(d.get("spring.config.activate.on-profile")))
                .findFirst().orElseThrow();
    }

    private static String main(String key) {
        Object v = mainDocument().get(key);
        return v == null ? null : String.valueOf(v);
    }

    @Test
    void mainDocument_backfillWindow_is60Seconds() {
        assertThat(main("telemetry.backfill.window-seconds")).isEqualTo("60");
    }

    @Test
    void mainDocument_bufferCapacity_is1024() {
        assertThat(main("telemetry.buffer.capacity")).isEqualTo("1024");
    }

    @Test
    void mainDocument_flywayLocations_isClasspathDbMigration() {
        assertThat(main("spring.flyway.locations")).isEqualTo("classpath:db/migration");
    }

    @Test
    void mainDocument_actuatorExposure_isHealthAndMetrics() {
        assertThat(main("management.endpoints.web.exposure.include")).isEqualTo("health,metrics");
    }

    @Test
    void mainDocument_loggingSettings_matchContract() {
        assertThat(main("logging.file.name")).isEqualTo("logs/telemetry-ingestion-processing.log");
        assertThat(main("logging.structured.format.file")).isEqualTo("ecs");
        assertThat(main("logging.logback.rollingpolicy.max-file-size")).isEqualTo("10MB");
        assertThat(main("logging.logback.rollingpolicy.max-history")).isEqualTo("7");
    }

    @Test
    void testProfileDocument_r2dbcUrl_isH2InMemory() {
        assertThat(String.valueOf(testDocument().get("spring.r2dbc.url")))
                .isEqualTo("r2dbc:h2:mem:///telemetrydb;DB_CLOSE_DELAY=-1;NON_KEYWORDS=VALUE");
    }

    @Test
    void testProfileDocument_flyway_isDisabled() {
        assertThat(String.valueOf(testDocument().get("spring.flyway.enabled"))).isEqualTo("false");
    }
}
