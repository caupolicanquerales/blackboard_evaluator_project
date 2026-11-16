package com.blackboard.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.ConfigurationPropertySources;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.MutablePropertySources;
import org.springframework.core.env.PropertySource;
import org.springframework.core.io.FileSystemResource;

class ApplicationYmlTest {

    private static final Path FILE = Path.of("src", "main", "resources", "application.yml");

    private PropertySource<?> base;
    private PropertySource<?> test;

    @BeforeEach
    void load() throws IOException {
        List<PropertySource<?>> docs = new YamlPropertySourceLoader()
                .load("application", new FileSystemResource(FILE));
        assertThat(docs).hasSize(2);
        base = docs.get(0);
        test = docs.get(1);
    }

    private static Object get(PropertySource<?> source, String key) {
        return source.getProperty(key);
    }

    @Test
    void load_twoDocuments_secondIsTestProfile() {
        assertThat(get(base, "spring.config.activate.on-profile")).isNull();
        assertThat(get(test, "spring.config.activate.on-profile")).isEqualTo("test");
    }

    @Test
    void base_connectionValues_areBarePlaceholders() {
        assertThat(get(base, "spring.application.name")).isEqualTo("telemetry-ingestion-processing");
        assertThat(get(base, "spring.r2dbc.url")).isEqualTo("${TELEMETRY_R2DBC_URL}");
        assertThat(get(base, "spring.r2dbc.username")).isEqualTo("${TELEMETRY_DB_USER}");
        assertThat(get(base, "spring.r2dbc.password")).isEqualTo("${TELEMETRY_DB_PASSWORD}");
        assertThat(get(base, "spring.flyway.enabled")).isEqualTo(true);
        assertThat(get(base, "spring.flyway.url")).isEqualTo("${TELEMETRY_JDBC_URL}");
        assertThat(get(base, "spring.flyway.user")).isEqualTo("${TELEMETRY_DB_USER}");
        assertThat(get(base, "spring.flyway.password")).isEqualTo("${TELEMETRY_DB_PASSWORD}");
        assertThat(get(base, "spring.flyway.locations")).isEqualTo("filesystem:db/migrations");
    }

    @Test
    void base_telemetrySettings_haveSpecifiedLiterals() {
        assertThat(get(base, "telemetry.reorder-window")).isEqualTo("PT60S");
        assertThat(get(base, "telemetry.reorder-buffer-capacity")).isEqualTo(4096);
        assertThat(get(base, "telemetry.validated-stream-capacity")).isEqualTo(1024);
        assertThat(get(base, "telemetry.broadcast-capacity")).isEqualTo(1024);
        assertThat(get(base, "telemetry.emit-retry-timeout")).isEqualTo("PT0.1S");
    }

    @Test
    void base_boundaries_haveSpecifiedEntries() {
        assertBoundary(0, "HEART_RATE", 30, 240, false, true);
        assertBoundary(1, "POWER", 0, 2500, false, true);
        assertBoundary(2, "CADENCE", 0, 220, false, true);
        assertBoundary(3, "SWIM_PACE", 45, 100000, true, true);
        assertBoundary(4, "GROUND_CONTACT_TIME", 0, 0, false, false);
        assertBoundary(5, "RESPIRATION", 0, 0, false, false);
        assertBoundary(6, "SWIM_STROKE", 0, 0, false, false);
        assertThat(get(base, "telemetry.boundaries[7].metric")).isNull();
    }

    private void assertBoundary(int i, String metric, int min, int max, boolean exclusive, boolean enabled) {
        String p = "telemetry.boundaries[" + i + "].";
        assertThat(get(base, p + "metric")).isEqualTo(metric);
        assertThat(Double.parseDouble(String.valueOf(get(base, p + "min")))).isEqualTo(min);
        assertThat(Double.parseDouble(String.valueOf(get(base, p + "max")))).isEqualTo(max);
        if (exclusive) {
            assertThat(get(base, p + "min-exclusive")).isEqualTo(true);
        }
        assertThat(get(base, p + "enabled")).isEqualTo(enabled);
    }

    @Test
    void base_observability_haveSpecifiedLiterals() {
        assertThat(get(base, "logging.level.root")).isEqualTo("INFO");
        assertThat(get(base, "logging.level.com.blackboard.telemetry")).isEqualTo("INFO");
        assertThat(get(base, "logging.file.name")).isEqualTo("logs/telemetry-ingestion-processing.log");
        assertThat(get(base, "logging.structured.format.file")).isEqualTo("ecs");
        assertThat(get(base, "logging.logback.rollingpolicy.max-file-size")).isEqualTo("10MB");
        assertThat(get(base, "logging.logback.rollingpolicy.max-history")).isEqualTo(7);
        assertThat(get(base, "management.endpoints.web.exposure.include")).isEqualTo("health,metrics");
    }

    @Test
    void testProfile_connectionValues_useEmbeddedH2() {
        assertThat(get(test, "spring.r2dbc.url"))
                .isEqualTo("r2dbc:h2:mem:///telemetry;DB_CLOSE_DELAY=-1;NON_KEYWORDS=VALUE");
        assertThat(get(test, "spring.r2dbc.username")).isEqualTo("sa");
        assertThat(String.valueOf(get(test, "spring.r2dbc.password"))).isEmpty();
        assertThat(get(test, "spring.flyway.enabled")).isEqualTo(true);
        assertThat(get(test, "spring.flyway.url"))
                .isEqualTo("jdbc:h2:mem:telemetry;DB_CLOSE_DELAY=-1;NON_KEYWORDS=VALUE");
        assertThat(get(test, "spring.flyway.user")).isEqualTo("sa");
        assertThat(String.valueOf(get(test, "spring.flyway.password"))).isEmpty();
        assertThat(get(test, "spring.flyway.locations")).isEqualTo("filesystem:db/migrations");
        assertThat(get(test, "logging.file.name")).isEqualTo("target/test-logs/telemetry.log");
    }

    @Test
    void base_document_containsNoH2Text() throws IOException {
        String baseText = Files.readString(FILE).split("(?m)^---\\s*$")[0];

        assertThat(baseText.toLowerCase()).doesNotContain("h2");
    }

    @Test
    void base_flywayUrl_isDistinctVariableFromR2dbcUrl() {
        assertThat(get(base, "spring.flyway.url")).isNotEqualTo(get(base, "spring.r2dbc.url"));
        assertThat(String.valueOf(get(test, "spring.flyway.url"))).startsWith("jdbc:")
                .isNotEqualTo(get(test, "spring.r2dbc.url"));
    }

    @Test
    void bind_telemetryProperties_hasSevenBoundaries() {
        MutablePropertySources sources = new MutablePropertySources();
        sources.addFirst(new MapPropertySource("base", flatten(base)));

        TelemetryProperties props = new Binder(ConfigurationPropertySources.from(sources))
                .bind("telemetry", TelemetryProperties.class).get();

        assertThat(props.reorderWindow()).isEqualTo(Duration.ofSeconds(60));
        assertThat(props.reorderBufferCapacity()).isEqualTo(4096);
        assertThat(props.emitRetryTimeout()).isEqualTo(Duration.ofMillis(100));
        assertThat(props.boundaries()).hasSize(7);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> flatten(PropertySource<?> source) {
        Map<String, Object> raw = (Map<String, Object>) source.getSource();
        Map<String, Object> out = new java.util.LinkedHashMap<>();
        raw.forEach((key, value) -> out.put(key,
                value instanceof org.springframework.boot.origin.OriginTrackedValue tracked
                        ? tracked.getValue() : value));
        return out;
    }
}
